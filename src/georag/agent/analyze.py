"""Analyze mode: question → plan → code from templates → sandboxed run → self-repair.

The model never writes free-form code. It fills a typed :class:`AnalysisPlan`; a Jinja
template turns the plan into a short, readable script that calls :mod:`georag.geo.eo`. Repairs
work on the plan too (wider cloud limit, neighbouring month, fewer scenes), which keeps every
attempt inside the same audited code path.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from georag.agent import prompts
from georag.agent.grounding import format_sources, make_citation
from georag.geo import gazetteer
from georag.llm import LLM
from georag.retrieval import Retriever
from georag.sandbox import StaticCheckError, run_script
from georag.schemas import AnalysisPlan, AnalyzeResult, Attempt, Citation, RetrievalToggles

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined, keep_trailing_newline=True)

MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}
SEASONS = {"winter": 1, "spring": 4, "summer": 7, "autumn": 10, "fall": 10}


def parse_periods(text: str) -> list[str]:
    """Find months in free text: '2020-02', 'February 2020', 'Feb 2020 vs Feb 2025', 'summer 2024'."""
    t = text.lower()
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])\b", t):
        found.append((m.start(), f"{m.group(1)}-{m.group(2)}"))
    month_re = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
    for m in re.finditer(rf"\b{month_re}\s+((?:19|20)\d{{2}})\b", t):
        found.append((m.start(), f"{m.group(2)}-{MONTHS[m.group(1)[:3]]:02d}"))
    # "February 2020 vs 2025": a bare year after a month inherits that month.
    for m in re.finditer(
        rf"\b{month_re}\s+((?:19|20)\d{{2}})\s*(?:vs\.?|versus|and|to|with|compared (?:to|with))\s*((?:19|20)\d{{2}})\b",
        t,
    ):
        found.append((m.start(3), f"{m.group(3)}-{MONTHS[m.group(1)[:3]]:02d}"))
    for m in re.finditer(r"\b(winter|spring|summer|autumn|fall)\s+(?:of\s+)?((?:19|20)\d{2})\b", t):
        found.append((m.start(), f"{m.group(2)}-{SEASONS[m.group(1)]:02d}"))
    if not found:
        # "a summer month" with a year somewhere else
        season = re.search(r"\b(winter|spring|summer|autumn|fall)\b", t)
        years = re.findall(r"\b((?:19|20)\d{2})\b", t)
        if season and years:
            found.append((0, f"{years[0]}-{SEASONS[season.group(1)]:02d}"))
    out: list[str] = []
    for _, p in sorted(found):
        if p not in out:
            out.append(p)
    return out


def heuristic_plan(question: str) -> AnalysisPlan:
    q = question.lower()
    periods = parse_periods(question)
    explicit = bool(periods)
    bbox = gazetteer.parse_bbox(question)
    place_hit = None if bbox else gazetteer.find_in_text(question)
    named = re.search(r"\b(?:of|at|around|for|in)\s+((?:[A-Z][\w'’.-]*\s?)+?)\s*\(\s*bbox", question)
    place = named.group(1).strip() if named else place_hit[0] if place_hit else "custom area"
    if bbox is None and place_hit:
        bbox = place_hit[1]
    if "ndvi" in q or "vegetation" in q or "green" in q:
        task, index = "ndvi", "NDVI"
    elif len(periods) >= 2 or any(w in q for w in ("change", " vs", "versus", "compare")):
        task, index = "water_change", "MNDWI"
    else:
        task, index = "water_extent", "MNDWI"
    if "ndwi" in q and "mndwi" not in q:
        index = "NDWI"
    if not periods:
        today = date.today()
        periods = [f"{today.year - 1}-{today.month:02d}"]
    if task == "water_change" and len(periods) == 1:
        y, m = periods[0].split("-")
        periods = [f"{int(y) - 5}-{m}", periods[0]]
    return AnalysisPlan(
        task=task,  # type: ignore[arg-type]
        place=place,
        bbox=bbox,
        periods=periods[:2] if task == "water_change" else periods[:1],
        index=index,  # type: ignore[arg-type]
        threshold=0.0,
        max_cloud=30.0,
        max_scenes=4,
        resolution=20,
        rationale=f"{'parsed from the request' if explicit else 'default period'}: {question}",
    )


_TASK_WORDS = re.compile(
    r"\b(water|lake|lagoon|reservoir|flood\w*|wetland|n?d[wv]i|mndwi|vegetation|greenness)\b", re.I
)


def _explicit_task(plan: AnalysisPlan) -> bool:
    return bool(_TASK_WORDS.search(plan.rationale.split(":", 1)[-1]))


def validate_plan(plan: AnalysisPlan, fallback: AnalysisPlan) -> AnalysisPlan:
    """Keep the model's judgement calls, but never let it invent geography or dates."""
    data = plan.model_dump()
    data["bbox"] = fallback.bbox  # from the gazetteer or the user, never from the model
    data["place"] = fallback.place
    if fallback.rationale.startswith("parsed from the request") or not all(
        re.fullmatch(r"(19|20)\d{2}-(0[1-9]|1[0-2])", p) for p in data["periods"]
    ):
        data["periods"] = fallback.periods
    if _explicit_task(fallback):
        # The request named the analysis (water, NDVI, an index); the model may tune it, not change it.
        data["task"] = fallback.task
        if fallback.task == "ndvi" or data["index"] == "NDVI":
            data["index"] = fallback.index
    if data["task"] == "ndvi":
        data["index"] = "NDVI"
    elif data["index"] == "NDVI":
        data["index"] = "MNDWI"
    need = 2 if data["task"] == "water_change" else 1
    if len(data["periods"]) < need:
        data["periods"] = fallback.periods
    data["periods"] = data["periods"][:need]
    data["max_cloud"] = float(min(80, max(5, data["max_cloud"])))
    data["max_scenes"] = int(min(6, max(1, data["max_scenes"])))
    data["threshold"] = float(min(0.4, max(-0.3, data["threshold"])))
    data["resolution"] = 20 if data["resolution"] not in (10, 20, 30, 60) else data["resolution"]
    return AnalysisPlan.model_validate(data)


def render(plan: AnalysisPlan, title: str, reference: bool = False) -> str:
    template = _env.get_template(f"{plan.task}.py.j2")
    plan_json = json.dumps(plan.model_dump(exclude={"rationale"}))
    return template.render(
        plan=plan,
        plan_json=plan_json,
        title=title.replace('"', "'"),
        place=plan.place.replace('"', "'"),
        bbox=tuple(round(v, 5) for v in plan.bbox) if plan.bbox else None,
        periods=plan.periods,
        reference=reference,
    )


def _shift_month(p: str, delta: int) -> str:
    y, m = (int(x) for x in p.split("-"))
    m += delta
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y}-{m:02d}"


def deterministic_repair(plan: AnalysisPlan, error: str, attempt: int) -> AnalysisPlan:
    data = plan.model_dump()
    err = error.lower()
    if "no sentinel-2" in err or "clear pixels" in err or "no scene" in err:
        if data["max_cloud"] < 60:
            data["max_cloud"] = min(80.0, data["max_cloud"] + 25)
        else:
            # Move only the month that failed, alternating forward and back.
            bad = next((p for p in data["periods"] if p in error), data["periods"][-1])
            shift = 1 if attempt % 2 else -1
            data["periods"] = [_shift_month(p, shift) if p == bad else p for p in data["periods"]]
        data["max_scenes"] = max(data["max_scenes"], 6)
    elif "memory" in err or "timeout" in err:
        data["max_scenes"] = max(1, data["max_scenes"] - 2)
        data["resolution"] = 30 if data["resolution"] < 30 else 60
    return AnalysisPlan.model_validate(data)


class AnalyzeAgent:
    def __init__(
        self,
        retriever: Retriever | None,
        llm: LLM | None,
        runs_dir: Path,
        timeout_s: int = 300,
        memory_mb: int = 4096,
        max_repairs: int = 3,
        allowed_hosts: list[str] | None = None,
    ):
        self.retriever = retriever
        self.llm = llm
        self.runs_dir = runs_dir
        self.timeout_s = timeout_s
        self.memory_mb = memory_mb
        self.max_repairs = max_repairs
        self.allowed_hosts = allowed_hosts

    def _method_notes(self, question: str, task: str) -> tuple[str, list[Citation]]:
        if self.retriever is None:
            return "(no corpus loaded)", []
        focus = (
            "NDVI vegetation index Sentinel-2 red near-infrared"
            if task == "ndvi"
            else "MNDWI water index threshold Sentinel-2 SWIR open water mapping"
        )
        passages, _ = self.retriever.retrieve(f"{focus} {question}", RetrievalToggles(), k=4)
        return format_sources(passages, max_chars=700), [
            make_citation(i + 1, p) for i, p in enumerate(passages)
        ]

    def plan(self, question: str, notes: str) -> AnalysisPlan:
        fallback = heuristic_plan(question)
        if self.llm is None:
            return fallback
        hint = json.dumps(fallback.model_dump(exclude={"bbox", "rationale"}))
        try:
            plan = self.llm.json(
                [
                    {"role": "system", "content": prompts.PLAN_SYSTEM.format(notes=notes)},
                    {
                        "role": "user",
                        "content": f"Request: {question}\nParsed so far (dates and place are reliable): {hint}",
                    },
                ],
                AnalysisPlan,
                max_tokens=300,
            )
            return validate_plan(plan, fallback)
        except Exception:
            return fallback

    def repair(self, plan: AnalysisPlan, error: str, attempt: int) -> AnalysisPlan:
        base = deterministic_repair(plan, error, attempt)
        if self.llm is None:
            return base
        try:
            proposal = self.llm.json(
                [
                    {"role": "system", "content": prompts.REPAIR_SYSTEM},
                    {
                        "role": "user",
                        "content": f"Plan: {plan.model_dump_json(exclude={'bbox'})}\nError: {error[-1500:]}",
                    },
                ],
                AnalysisPlan,
                max_tokens=300,
            )
            fixed = validate_plan(proposal, plan)
        except Exception:
            return base
        # A model "repair" that changes nothing is replaced by the deterministic one.
        same = fixed.model_dump(exclude={"rationale"}) == plan.model_dump(exclude={"rationale"})
        return base if same else fixed

    def run(
        self, question: str, emit=lambda e: None, reference: bool = False, run_id: str | None = None
    ) -> AnalyzeResult:
        t0 = time.perf_counter()
        run_id = run_id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        first = heuristic_plan(question)
        notes, citations = self._method_notes(question, first.task)
        plan = self.plan(question, notes)
        if plan.bbox is None:
            raise ValueError(
                "Unknown study area: name a place from the gazetteer or give a bounding box 'lon_min, lat_min, lon_max, lat_max'."
            )
        emit({"type": "plan", "plan": plan.model_dump()})
        title = {
            "water_change": f"Open water at {plan.place}: {' vs '.join(plan.periods)}",
            "water_extent": f"Open water at {plan.place}, {plan.periods[0]}",
            "ndvi": f"NDVI at {plan.place}, {plan.periods[0]}",
        }[plan.task]

        attempts: list[Attempt] = []
        code = ""
        ok = False
        for n in range(1, self.max_repairs + 2):
            code = render(plan, title, reference)
            emit({"type": "code", "attempt": n, "code": code})
            try:
                res = run_script(code, run_dir, self.timeout_s, self.memory_mb, self.allowed_hosts)
                att = Attempt(
                    n=n,
                    plan=plan,
                    code=code,
                    ok=res.ok,
                    seconds=round(res.seconds, 1),
                    stdout=res.stdout[-4000:],
                    stderr=res.stderr[-4000:],
                    error=res.error,
                )
            except StaticCheckError as exc:
                att = Attempt(n=n, plan=plan, code=code, ok=False, seconds=0.0, error=f"static check: {exc}")
            attempts.append(att)
            emit({"type": "attempt", "attempt": att.model_dump(exclude={"code"})})
            if att.ok:
                ok = True
                break
            if n > self.max_repairs:
                break
            plan = self.repair(plan, (att.stderr or "") + "\n" + (att.error or ""), n)
            emit({"type": "repair", "plan": plan.model_dump()})

        outputs, numbers = {}, {}
        result_file = run_dir / "result.json"
        if ok and result_file.exists():
            data = json.loads(result_file.read_text())
            numbers = data.get("numbers", {})
            outputs["layers"] = json.dumps(data.get("layers", {}))
        for f in sorted(run_dir.iterdir()):
            if f.suffix in (".png", ".tif", ".py", ".json") and not f.name.startswith("."):
                outputs[f.name] = f.name
        (run_dir / "attempts.json").write_text(json.dumps([a.model_dump() for a in attempts], indent=2))
        result = AnalyzeResult(
            question=question,
            plan=plan,
            code=code,
            attempts=attempts,
            ok=ok,
            run_id=run_id,
            outputs=outputs,
            numbers=numbers,
            citations=citations,
            explanation=explain(plan, numbers)
            if ok
            else f"The analysis failed after {len(attempts)} attempts: {attempts[-1].error}",
            timings={"total": time.perf_counter() - t0},
        )
        (run_dir / "analysis.json").write_text(result.model_dump_json(indent=2))
        return result


def explain(plan: AnalysisPlan, n: dict) -> str:
    if plan.task == "water_change" and "water_km2_a" in n:
        a, b = n["periods"][0], n["periods"][1]
        txt = (
            f"Open water at {plan.place} covered {n['water_km2_a']:.1f} km² in {a['month']} and {n['water_km2_b']:.1f} km² in {b['month']} "
            f"({n['change_km2']:+.1f} km², {n['change_pct']:+.0f} %), measured on the {n['comparable_fraction']:.0%} of the area that was cloud-free in both months. "
            f"{n['gained_km2']:.1f} km² became water and {n['lost_km2']:.1f} km² dried out. "
            f"Composites used {len(a['scenes'])} and {len(b['scenes'])} Sentinel-2 scenes ({', '.join(a['scene_dates'])}; {', '.join(b['scene_dates'])}); "
            f"water is {plan.index} > {plan.threshold:g} (Otsu thresholds would be {a['otsu_threshold']:+.2f} and {b['otsu_threshold']:+.2f})."
        )
        return txt
    if plan.task == "water_extent" and "water_km2" in n:
        txt = f"Open water at {plan.place} in {n['month']}: {n['water_km2']:.1f} km² ({plan.index} > {plan.threshold:g}, {len(n['scenes'])} scenes, {n['observed_fraction']:.0%} of the area observed)."
        if n.get("reference_km2") is not None:
            txt += f" The JRC Global Surface Water reference (occurrence ≥ 50 %, 1984–2021) gives {n['reference_km2']:.1f} km²; IoU {n['iou_vs_reference']:.2f}."
        return txt
    if plan.task == "ndvi" and "mean" in n:
        cf = n["class_fractions"]
        return (
            f"Mean NDVI at {plan.place} in {n['month']} was {n['mean']:.2f} (median {n['median']:.2f}, 10–90 % range {n['p10']:.2f}–{n['p90']:.2f}) "
            f"from {len(n['scenes'])} scenes. {cf['dense(>=0.5)']:.0%} of observed pixels are dense vegetation (NDVI ≥ 0.5), "
            f"{cf['sparse(0.2-0.5)']:.0%} sparse and {cf['bare_or_water(<0.2)']:.0%} bare soil, built-up or water."
        )
    return ""
