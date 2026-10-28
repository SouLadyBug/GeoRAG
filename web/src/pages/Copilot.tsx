import hljs from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";
import "highlight.js/styles/github-dark-dimmed.css";
import { BookOpen, Code2, FlaskConical, Map as MapIcon, MessageSquareText, Network, Send, Sparkles, Square, Wand2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { asset, detectBackend, type Health, loadDemos, replayDemo, runLive } from "../api";
import { CitedMarkdown, CitedSentences } from "../components/Cited";
import GraphView, { TYPE_COLORS } from "../components/GraphView";
import MapPanel from "../components/MapPanel";
import type { AnalyzeResult, AskResult, Citation, DemoEntry, DesignResult, ExploreResult, Mode, Passage, StreamEvent, Toggles, Turn } from "../types";

hljs.registerLanguage("python", python);

const MODES: { id: Mode; label: string; icon: any }[] = [
  { id: "ask", label: "Ask", icon: MessageSquareText },
  { id: "analyze", label: "Analyze", icon: MapIcon },
  { id: "design", label: "Design", icon: FlaskConical },
  { id: "explore", label: "Explore", icon: Network },
];

type Tab = "sources" | "map" | "code" | "graph";

const uid = () => Math.random().toString(36).slice(2, 10);

function Steps({ turn }: { turn: Turn }) {
  const items: { key: string; text: string; state: "ok" | "run" | "err" }[] = [];
  let tokens = 0;
  for (const e of turn.events) {
    if (e.type === "route") items.push({ key: "route", text: `Routed to ${e.mode} — ${e.reason}`, state: "ok" });
    else if (e.type === "retrieval") {
      const lists = Object.entries(e.lists ?? {})
        .map(([k, v]) => `${k} ${v}`)
        .join(" · ");
      items.push({ key: "ret", text: `Retrieved ${e.passages.length} passages after fusion and reranking (${lists})`, state: "ok" });
    } else if (e.type === "token") tokens++;
    else if (e.type === "plan") items.push({ key: "plan", text: `Plan: ${e.plan.task} · ${e.plan.place} · ${e.plan.periods.join(" vs ")} · ${e.plan.index} > ${e.plan.threshold}`, state: "ok" });
    else if (e.type === "code") items.push({ key: `code${e.attempt}`, text: `Generated analysis script (attempt ${e.attempt})`, state: "ok" });
    else if (e.type === "attempt")
      items.push({ key: `att${e.attempt.n}`, text: e.attempt.ok ? `Sandbox run succeeded in ${e.attempt.seconds.toFixed(0)} s` : `Sandbox run failed: ${e.attempt.error}`, state: e.attempt.ok ? "ok" : "err" });
    else if (e.type === "repair") items.push({ key: `rep${items.length}`, text: `Self-repair: max cloud ${e.plan.max_cloud}% · periods ${e.plan.periods.join(", ")}`, state: "ok" });
    else if (e.type === "section") items.push({ key: `sec${e.section.key}`, text: `Wrote “${e.section.heading}”`, state: "ok" });
    else if (e.type === "graph") items.push({ key: "graph", text: `Knowledge subgraph: ${e.nodes.length} concepts, ${e.edges.length} links`, state: "ok" });
  }
  if (tokens && !turn.done) items.push({ key: "gen", text: `Generating answer · ${tokens} tokens`, state: "run" });
  if (!turn.done) {
    const last = turn.events[turn.events.length - 1];
    if (!last) items.push({ key: "start", text: "Routing the request…", state: "run" });
    else if (last.type === "route") items.push({ key: "r2", text: turn.mode === "analyze" ? "Retrieving method notes and planning…" : "Retrieving passages…", state: "run" });
    else if (last.type === "code") items.push({ key: "r3", text: "Running in the sandbox (Sentinel-2 download and processing)…", state: "run" });
    else if (last.type === "section_start") items.push({ key: "r4", text: `Writing “${last.heading}”…`, state: "run" });
  }
  return (
    <div className="steps">
      {items.map((s) => (
        <div className="step" key={s.key}>
          {s.state === "run" ? <span className="spin" /> : s.state === "ok" ? <span className="ok">✓</span> : <span className="err">✕</span>}
          <span>{s.text}</span>
        </div>
      ))}
    </div>
  );
}

function AnswerView({ turn, active, onCite }: { turn: Turn; active: number | null; onCite: (n: number) => void }) {
  const r = turn.result;
  if (turn.error) return <div className="refusal">{turn.error}</div>;
  if (!r) return turn.streamed ? <div className="answer"><p>{turn.streamed.replace(/\s*\[\d+(?:,\s*\d+)*\]/g, "")}<span className="faint">▍</span></p></div> : null;
  if (r.mode === "ask") {
    const a = r as AskResult;
    if (a.refused)
      return (
        <div className="refusal">
          <b>Not enough evidence.</b> {a.refusal_reason} GeoRAG answers only from its corpus, so it declines rather than guesses.
        </div>
      );
    return (
      <div className="answer">
        <CitedSentences sentences={a.sentences} active={active} onPick={onCite} />
        <div className="meta-row">
          {a.faithfulness != null && <span className={`chip ${a.faithfulness >= 0.99 ? "good" : "warn"}`}>{Math.round(a.faithfulness * 100)} % of sentences supported</span>}
          <span className="chip">{a.citations.length} sources cited</span>
          {a.timings.total != null && <span className="chip">{a.timings.total.toFixed(1)} s</span>}
        </div>
        {a.related.length > 0 && (
          <div className="meta-row">
            <span className="faint" style={{ fontSize: 12 }}>Related in the graph:</span>
            {a.related.map((x) => (
              <span key={x} className="chip entity">{x}</span>
            ))}
          </div>
        )}
      </div>
    );
  }
  if (r.mode === "design") {
    const d = r as DesignResult;
    return (
      <div>
        <h3 style={{ fontSize: 17, marginBottom: 14 }}>{d.title}</h3>
        {d.sections.map((s) => (
          <div className="design-sec" key={s.key}>
            <h4>
              {s.heading}
              {s.supported_ratio != null && <span className={`chip ${s.supported_ratio >= 0.99 ? "good" : "warn"}`} style={{ fontSize: 11 }}>{Math.round(s.supported_ratio * 100)} % supported</span>}
            </h4>
            <CitedMarkdown markdown={s.markdown} onPick={onCite} />
          </div>
        ))}
        <div className="meta-row">
          {d.faithfulness != null && <span className="chip good">{Math.round(d.faithfulness * 100)} % of statements supported</span>}
          <span className="chip">{d.citations.length} references</span>
        </div>
      </div>
    );
  }
  if (r.mode === "explore") {
    const x = r as ExploreResult;
    const label = Object.fromEntries(x.nodes.map((n) => [n.id, n]));
    return (
      <div className="answer">
        <div className="meta-row" style={{ marginTop: 0, marginBottom: 10 }}>
          {x.nodes
            .filter((n) => n.seed)
            .map((n) => (
              <span key={n.id} className="chip">
                <span className="sw" style={{ background: TYPE_COLORS[n.type] }} />
                {n.label}
              </span>
            ))}
        </div>
        {x.paths.slice(0, 4).map((p, i) => (
          <div key={i} className="mono" style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 4 }}>
            {p.map((id) => label[id]?.label ?? id).join("  →  ")}
          </div>
        ))}
        {x.summary && <CitedMarkdown markdown={x.summary} onPick={onCite} />}
        <div className="meta-row">
          <span className="chip">{x.nodes.length} concepts</span>
          <span className="chip">{x.edges.length} links</span>
          <span className="chip">{Object.keys(x.passages).length} supporting passages</span>
        </div>
      </div>
    );
  }
  const an = r as AnalyzeResult;
  return (
    <div className="answer">
      <p>{an.explanation}</p>
      {an.ok && an.outputs["map.png"] && (
        <figure className="figure" style={{ margin: "10px 0" }}>
          <img src={`${turn.assetBase}/map.png`} alt="Analysis map" />
        </figure>
      )}
      <div className="meta-row">
        <span className={`chip ${an.ok ? "good" : "warn"}`}>{an.ok ? "executed" : "failed"} · {an.attempts.length} attempt{an.attempts.length > 1 ? "s" : ""}</span>
        <span className="chip">{an.plan.index} &gt; {an.plan.threshold}</span>
        {Object.keys(an.outputs)
          .filter((k) => k.endsWith(".tif"))
          .map((k) => (
            <a key={k} className="chip" href={`${turn.assetBase}/${k}`} download>
              {k}
            </a>
          ))}
      </div>
    </div>
  );
}

function SourcesPanel({ citations, passages, active, onPick }: { citations: Citation[]; passages: Passage[]; active: number | null; onPick: (n: number) => void }) {
  const refs = useRef<Record<number, HTMLDivElement | null>>({});
  useEffect(() => {
    if (active != null) refs.current[active]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [active]);
  if (!citations.length && !passages.length) return <div className="placeholder">Cited passages appear here. Click a citation chip to jump to its source.</div>;
  const cited = new Set(citations.map((c) => c.chunk_id));
  return (
    <div className="panel-scroll">
      {citations.length > 0 && <div className="side-h">Cited</div>}
      <div className="sources-list">
        {citations.map((c) => (
          <div key={c.n} ref={(el) => (refs.current[c.n] = el)} className={`src${active === c.n ? " active" : ""}`} onClick={() => onPick(c.n)}>
            <span className="n">[{c.n}]</span>
            <div>
              <div className="t">{c.title}</div>
              <div className="s">
                {c.year ?? ""} {c.section && c.section !== "Abstract" ? `· ${c.section}` : ""} {c.url && <a href={c.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>open ↗</a>}
              </div>
              <div className="quote">{c.quote}</div>
            </div>
          </div>
        ))}
      </div>
      {passages.filter((p) => !cited.has(p.chunk.chunk_id)).length > 0 && <div className="side-h" style={{ marginTop: 22 }}>Also retrieved</div>}
      <div className="sources-list">
        {passages
          .filter((p) => !cited.has(p.chunk.chunk_id))
          .map((p) => (
            <div key={p.chunk.chunk_id} className="src" style={{ gridTemplateColumns: "1fr" }}>
              <div>
                <div className="t" style={{ fontWeight: 550 }}>{p.chunk.title}</div>
                <div className="s">
                  {p.chunk.domain.replace("_", " ")} · {Object.entries(p.sources).map(([k, v]) => `${k} #${v}`).join(" · ")}
                  {p.rerank_score != null && ` · rerank ${p.rerank_score.toFixed(2)}`}
                </div>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}

function CodePanel({ result }: { result: AnalyzeResult | null }) {
  const html = useMemo(() => (result?.code ? hljs.highlight(result.code, { language: "python" }).value : ""), [result]);
  if (!result) return <div className="placeholder">The generated Python script and every repair attempt appear here.</div>;
  return (
    <div className="panel-scroll code-wrap">
      <div className="side-h">Attempts</div>
      {result.attempts.map((a) => (
        <div key={a.n} className={`attempt ${a.ok ? "ok" : "fail"}`}>
          <b>Attempt {a.n}</b> · {a.ok ? "succeeded" : "failed"} · {a.seconds.toFixed(0)} s · max cloud {a.plan.max_cloud}% · {a.plan.periods.join(", ")}
          {a.error && <pre>{a.error}</pre>}
          {a.ok && a.stdout && <pre>{a.stdout.split("\n").slice(0, 14).join("\n")}</pre>}
        </div>
      ))}
      <div className="side-h" style={{ marginTop: 18 }}>Final script · sandboxed, network allow-listed</div>
      <pre>
        <code className="hljs language-python" dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
    </div>
  );
}

export default function Copilot() {
  const [health, setHealth] = useState<Health | null | undefined>(undefined);
  const [demos, setDemos] = useState<DemoEntry[]>([]);
  const [mode, setMode] = useState<Mode | "auto">("auto");
  const [toggles, setToggles] = useState<Toggles>({ bm25: true, dense: true, graph: true, rerank: true, figures: false });
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [tab, setTab] = useState<Tab>("sources");
  const [active, setActive] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const threadEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    detectBackend().then(setHealth);
    loadDemos().then(setDemos);
  }, []);

  useEffect(() => {
    const q = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("demo");
    if (q && demos.length && !turns.length) {
      const d = demos.find((x) => x.id === q);
      if (d) start(d.question, d);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demos]);

  useEffect(() => threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [turns]);

  const live = !!health;
  const focus = [...turns].reverse().find((t) => t.result) ?? null;
  const focusResult = focus?.result ?? null;
  const analyze = (focusResult?.mode === "analyze" ? focusResult : null) as AnalyzeResult | null;
  const explore = (focusResult?.mode === "explore" ? focusResult : null) as ExploreResult | null;
  const citations = focusResult && "citations" in focusResult ? focusResult.citations : [];
  const passages = focusResult?.mode === "ask" ? (focusResult as AskResult).passages : [];

  function update(id: string, fn: (t: Turn) => Turn) {
    setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));
  }

  async function start(question: string, demo?: DemoEntry) {
    if (!question.trim() || busy) return;
    const id = uid();
    const d = demo ?? demos.find((x) => x.question.trim().toLowerCase() === question.trim().toLowerCase());
    const assetBase = d ? asset(`demo/${d.id}`) : "";
    setTurns((ts) => [...ts, { id, question, mode: null, events: [], streamed: "", result: null, error: null, done: false, assetBase }]);
    setInput("");
    setBusy(true);
    setActive(null);
    const ctrl = new AbortController();
    abort.current = ctrl;
    const onEvent = (e: StreamEvent) => {
      update(id, (t) => {
        const next = { ...t, events: e.type === "token" ? t.events.concat(e) : [...t.events, e] };
        if (e.type === "route") next.mode = e.mode;
        if (e.type === "token") next.streamed = t.streamed + e.text;
        if (e.type === "result") {
          next.result = e.result;
          next.done = true;
          if (!d && e.result.mode === "analyze") next.assetBase = `/api/runs/${e.result.run_id}`;
        }
        if (e.type === "error") {
          next.error = e.message;
          next.done = true;
        }
        return next;
      });
      if (e.type === "result") setTab(e.result.mode === "analyze" ? "map" : e.result.mode === "explore" ? "graph" : "sources");
    };
    try {
      if (live && !d) await runLive(question, mode, toggles, onEvent, ctrl.signal);
      else if (d) await replayDemo(d.id, onEvent, ctrl.signal);
      else
        onEvent({
          type: "error",
          message: "This is the static showcase: it replays recorded runs. Pick one of the examples, or run GeoRAG locally (make serve) to ask your own questions.",
        });
    } catch (err: any) {
      if (err?.name !== "AbortError") onEvent({ type: "error", message: String(err?.message ?? err) });
    } finally {
      update(id, (t) => ({ ...t, done: true }));
      setBusy(false);
    }
  }

  const onCite = (n: number) => {
    setActive(n);
    setTab("sources");
  };

  return (
    <div className="copilot">
      <aside className="sidebar">
        <div className="side-h">Mode</div>
        <div className="mode-switch">
          <button className={`mode-btn auto${mode === "auto" ? " on" : ""}`} onClick={() => setMode("auto")}>
            <Wand2 size={15} /> Auto-route
          </button>
          {MODES.map((m) => (
            <button key={m.id} className={`mode-btn${mode === m.id ? " on" : ""}`} onClick={() => setMode(m.id)}>
              <m.icon size={15} /> {m.label}
            </button>
          ))}
        </div>

        <div className="side-h">Retrieval components</div>
        {(["bm25", "dense", "graph", "rerank", "figures"] as const).map((k) => (
          <div className="toggle" key={k}>
            <span>{{ bm25: "BM25 (sparse)", dense: "Dense · Qwen3-Embedding", graph: "Knowledge graph", rerank: "Reranker · Qwen3-Reranker", figures: "Figure index" }[k]}</span>
            <button className={`sw${toggles[k] ? " on" : ""}`} disabled={!live || k === "figures"} onClick={() => setToggles((t) => ({ ...t, [k]: !t[k] }))} aria-label={k} />
          </div>
        ))}
        <div className="faint" style={{ fontSize: 11.5, marginTop: 4 }}>{live ? "Switch components off to see what each one adds." : "Live ablation switches work with the local backend."}</div>

        <div className="side-h">Recorded runs</div>
        {demos.map((d) => (
          <button key={d.id} className="example-btn" onClick={() => start(d.question, d)} disabled={busy}>
            <span className="m">{d.mode}</span>
            {d.title}
          </button>
        ))}

        <div className="side-h">Engine</div>
        <div className="status-pill" style={{ width: "100%" }}>
          <span className={`dot ${live ? "live" : "demo"}`} />
          {health === undefined ? "Connecting…" : live ? `Live · ${health!.llm.model}` : "Showcase · recorded runs"}
        </div>
      </aside>

      <section className="thread-col">
        <div className="thread">
          {turns.length === 0 ? (
            <div className="empty">
              <div>
                <div className="avatar bot" style={{ width: 48, height: 48, margin: "0 auto 16px", borderRadius: 14 }}>
                  <Sparkles size={22} />
                </div>
                <h3>Ask the geospatial literature — and the satellites</h3>
                <p style={{ maxWidth: 460, margin: "0 auto" }}>
                  Cited answers, executable Sentinel-2 analyses, study designs and a knowledge graph across GIS, remote sensing, LiDAR, digital twins and geospatial computer vision.
                </p>
              </div>
            </div>
          ) : (
            turns.map((t) => (
              <div className="turn" key={t.id}>
                <div className="q">
                  <div className="avatar user">You</div>
                  <div className="bubble">{t.question}</div>
                </div>
                <div className="a">
                  <div className="avatar bot">G</div>
                  <div className="body">
                    {t.mode && (
                      <div className="route-tag">
                        <b>{t.mode}</b>
                      </div>
                    )}
                    <Steps turn={t} />
                    <AnswerView turn={t} active={t === focus ? active : null} onCite={onCite} />
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={threadEnd} />
        </div>
        <div className="composer">
          <div className="composer-box">
            <textarea
              rows={1}
              value={input}
              placeholder={live ? "Ask a question, request an analysis, a study design, or how two concepts connect…" : "Showcase mode: pick a recorded run on the left (or run GeoRAG locally)"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  start(input);
                }
              }}
            />
            {busy ? (
              <button className="btn small" onClick={() => abort.current?.abort()}>
                <Square size={14} /> Stop
              </button>
            ) : (
              <button className="btn small primary" onClick={() => start(input)} disabled={!input.trim()}>
                <Send size={14} /> Send
              </button>
            )}
          </div>
          <div className="hint">
            <span>Answers cite passages from {health?.corpus?.documents ?? "the"} indexed documents; unsupported sentences are flagged.</span>
            <span>Enter to send</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="tabs">
          <button className={`tab${tab === "sources" ? " on" : ""}`} onClick={() => setTab("sources")}>
            <BookOpen size={14} /> Sources {citations.length > 0 && <span className="count">{citations.length}</span>}
          </button>
          <button className={`tab${tab === "map" ? " on" : ""}`} onClick={() => setTab("map")}>
            <MapIcon size={14} /> Map
          </button>
          <button className={`tab${tab === "code" ? " on" : ""}`} onClick={() => setTab("code")}>
            <Code2 size={14} /> Code
          </button>
          <button className={`tab${tab === "graph" ? " on" : ""}`} onClick={() => setTab("graph")}>
            <Network size={14} /> Graph
          </button>
        </div>
        <div className="panel-body">
          <div style={{ display: tab === "sources" ? "block" : "none", position: "absolute", inset: 0 }}>
            <SourcesPanel citations={citations} passages={passages} active={active} onPick={setActive} />
          </div>
          <div style={{ display: tab === "map" ? "block" : "none", position: "absolute", inset: 0 }}>
            <MapPanel result={analyze} assetBase={focus?.assetBase ?? ""} />
          </div>
          <div style={{ display: tab === "code" ? "block" : "none", position: "absolute", inset: 0 }}>
            <CodePanel result={analyze} />
          </div>
          <div style={{ display: tab === "graph" ? "block" : "none", position: "absolute", inset: 0 }}>
            {explore ? <GraphView nodes={explore.nodes} edges={explore.edges} paths={explore.paths} passages={explore.passages} /> : <div className="placeholder">Explore mode draws the concept subgraph here.</div>}
          </div>
        </div>
      </section>
    </div>
  );
}
