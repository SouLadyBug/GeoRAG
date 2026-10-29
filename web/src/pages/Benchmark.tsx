import Chart, { AXIS, TOOLTIP } from "../components/Chart";
import type { SiteData } from "../site";
import { pct } from "../site";

const SHORT: Record<string, string> = {
  BM25: "BM25",
  Dense: "Dense",
  "Hybrid (RRF)": "Hybrid",
  "Hybrid + graph": "+ graph",
  "Hybrid + rerank": "+ rerank",
  "Full: hybrid + graph + rerank": "Full",
};

export function RetrievalChart({ site, metric }: { site: SiteData; metric: "recall@5" | "mrr@10" | "ndcg@10" | "all@8" }) {
  const configs = site.benchmark.retrieval!.configs;
  const names = Object.keys(configs);
  const fact = names.map((n) => configs[n].summary.factual?.[metric] ?? null);
  const cross = names.map((n) => configs[n].summary.cross?.[metric] ?? null);
  const paraConfigs = site.benchmark.retrieval_paraphrased?.configs;
  const para = paraConfigs ? names.map((n) => paraConfigs[n]?.summary.paraphrased?.[metric] ?? null) : null;
  const label = { show: true, position: "top", color: "#cbd5e1", fontSize: 10, formatter: (p: any) => (p.value == null ? "" : `${Math.round(p.value * 100)}`) };
  const option = {
    grid: { left: 50, right: 20, top: 40, bottom: 40 },
    tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v: number) => (v == null ? "—" : v.toFixed(3)) },
    legend: { top: 0, textStyle: { color: "#94a3b8" }, itemWidth: 12, itemHeight: 12 },
    xAxis: { type: "category", data: names.map((n) => SHORT[n] ?? n), ...AXIS },
    yAxis: { type: "value", min: 0, max: 1, ...AXIS, axisLabel: { ...AXIS.axisLabel, formatter: (v: number) => `${Math.round(v * 100)}%` } },
    series: [
      { name: "Factual · generated wording", type: "bar", data: fact, barMaxWidth: 26, itemStyle: { color: "#2dd4bf", borderRadius: [4, 4, 0, 0] }, label },
      ...(para ? [{ name: "Factual · paraphrased", type: "bar", data: para, barMaxWidth: 26, itemStyle: { color: "#a78bfa", borderRadius: [4, 4, 0, 0] }, label }] : []),
      { name: metric === "recall@5" ? "Cross-domain · both passages" : "Cross-domain", type: "bar", data: cross, barMaxWidth: 26, itemStyle: { color: "#38bdf8", borderRadius: [4, 4, 0, 0] }, label },
    ],
  };
  return <Chart option={option} />;
}

function AnalyzeScatter({ items }: { items: any[] }) {
  const ok = items.filter((r) => r.ok && r.reference_km2 != null);
  const max = Math.max(10, ...ok.map((r) => Math.max(r.water_km2, r.reference_km2))) * 1.08;
  const option = {
    grid: { left: 60, right: 24, top: 20, bottom: 50 },
    tooltip: { ...TOOLTIP, formatter: (p: any) => `${p.data[2]} · ${p.data[3]}<br/>GeoRAG ${p.data[1].toFixed(1)} km² · JRC ${p.data[0].toFixed(1)} km²` },
    xAxis: { type: "log", name: "JRC GSW reference (km²)", nameLocation: "middle", nameGap: 30, nameTextStyle: { color: "#94a3b8" }, min: 0.5, max, ...AXIS },
    yAxis: { type: "log", name: "GeoRAG Analyze (km²)", nameLocation: "middle", nameGap: 44, nameTextStyle: { color: "#94a3b8" }, min: 0.5, max, ...AXIS },
    series: [
      { type: "line", data: [[0.5, 0.5], [max, max]], showSymbol: false, lineStyle: { color: "#475569", type: "dashed" }, silent: true },
      { type: "scatter", symbolSize: 11, data: ok.map((r) => [r.reference_km2, r.water_km2, r.lake, r.month]), itemStyle: { color: "#2dd4bf", borderColor: "#060a13", borderWidth: 1 } },
    ],
  };
  return <Chart option={option} className="chart tall" />;
}

function CorpusChart({ site }: { site: SiteData }) {
  const years = Object.keys(site.corpus.papers_by_year).sort();
  const option = {
    grid: { left: 44, right: 16, top: 16, bottom: 30 },
    tooltip: { ...TOOLTIP, trigger: "axis" },
    xAxis: { type: "category", data: years, ...AXIS },
    yAxis: { type: "value", ...AXIS },
    series: [{ type: "bar", data: years.map((y) => site.corpus.papers_by_year[y]), itemStyle: { color: "#2dd4bf", borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 }],
  };
  return <Chart option={option} className="chart" />;
}

export default function Benchmark({ site }: { site: SiteData | null }) {
  if (!site) return <div className="container section muted">Loading results…</div>;
  const r = site.benchmark.retrieval;
  const a = site.benchmark.answers;
  const small = site.benchmark.answers_small;
  const an = site.benchmark.analyze;
  const metrics = ["recall@5", "recall@10", "mrr@10", "ndcg@10"] as const;
  const best = (subset: "factual" | "cross", m: string) => Math.max(...Object.values(r?.configs ?? {}).map((c: any) => c.summary[subset]?.[m] ?? 0));
  return (
    <div className="page">
      <section className="section" style={{ paddingBottom: 30 }}>
        <div className="container">
          <div className="eyebrow">GeoRAG-Bench · results</div>
          <h2 className="title">Measured, not claimed</h2>
          <p className="lead">
            Every number on this page is read from <code>results/</code>, produced by <code>make eval</code> on the hardware listed below. The question sets, their construction and their biases are described under limitations.
          </p>
          <div className="grid-4" style={{ marginTop: 26 }}>
            <div className="card kpi">
              <div className="l">Generator</div>
              <div style={{ fontWeight: 700, marginTop: 4 }}>{site.models.generator}</div>
              <div className="d">tier: {site.models.tier}</div>
            </div>
            <div className="card kpi">
              <div className="l">Embedding · reranker</div>
              <div style={{ fontWeight: 700, marginTop: 4, fontSize: 14 }}>{site.models.embedding.split("/").pop()}</div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{site.models.reranker.split("/").pop()}</div>
            </div>
            <div className="card kpi">
              <div className="l">Hardware</div>
              <div style={{ fontWeight: 700, marginTop: 4, fontSize: 14 }}>{site.models.hardware}</div>
            </div>
            <div className="card kpi">
              <div className="l">Benchmark size</div>
              <div style={{ fontWeight: 700, marginTop: 4, fontSize: 14 }}>
                {Object.entries(site.benchmark.bench_sizes ?? {})
                  .map(([k, v]) => `${v} ${k}`)
                  .join(" · ")}
              </div>
            </div>
          </div>
        </div>
      </section>

      {r && (
        <section className="section-tight">
          <div className="container">
            <h3 style={{ fontSize: 22, marginBottom: 6 }}>Retrieval ablation</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Gold passage = the chunk a question was generated from (two chunks for cross-domain questions). Generated questions reuse their passage's wording, which flatters BM25; the paraphrased set rewords the same questions to limit that overlap. k = 10 after fusion; the reranker scores the top 20 fused candidates (CPU tier).
            </p>
            <div className="grid-2">
              <div className="card" style={{ padding: "16px 10px 6px" }}>
                <div className="faint" style={{ padding: "0 10px", fontSize: 13 }}>Recall@5</div>
                <RetrievalChart site={site} metric="recall@5" />
              </div>
              <div className="card" style={{ padding: "16px 10px 6px" }}>
                <div className="faint" style={{ padding: "0 10px", fontSize: 13 }}>nDCG@10</div>
                <RetrievalChart site={site} metric="ndcg@10" />
              </div>
            </div>
            <div className="card" style={{ marginTop: 20, overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Configuration</th>
                    {metrics.map((m) => (
                      <th key={m} className="num">
                        Factual {m}
                      </th>
                    ))}
                    {site.benchmark.retrieval_paraphrased && <th className="num">Paraphrased R@5</th>}
                    {site.benchmark.retrieval_paraphrased && <th className="num">Paraphrased nDCG@10</th>}
                    <th className="num">Cross both@8</th>
                    <th className="num">Cross nDCG@10</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(r.configs).map(([name, c]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      {metrics.map((m) => (
                        <td key={m} className={`num${c.summary.factual[m] === best("factual", m) ? " best" : ""}`}>
                          {c.summary.factual[m].toFixed(3)}
                        </td>
                      ))}
                      {site.benchmark.retrieval_paraphrased && <td className="num">{site.benchmark.retrieval_paraphrased.configs[name]?.summary.paraphrased?.["recall@5"].toFixed(3) ?? "—"}</td>}
                      {site.benchmark.retrieval_paraphrased && <td className="num">{site.benchmark.retrieval_paraphrased.configs[name]?.summary.paraphrased?.["ndcg@10"].toFixed(3) ?? "—"}</td>}
                      <td className={`num${c.summary.cross?.["all@8"] === best("cross", "all@8") ? " best" : ""}`}>{c.summary.cross?.["all@8"].toFixed(3) ?? "—"}</td>
                      <td className={`num${c.summary.cross?.["ndcg@10"] === best("cross", "ndcg@10") ? " best" : ""}`}>{c.summary.cross?.["ndcg@10"].toFixed(3) ?? "—"}</td>
                    </tr>
                  ))}
                  <tr>
                    <td className="faint">+ figure index</td>
                    <td className="num faint" colSpan={8} style={{ textAlign: "left" }}>
                      not evaluated — the abstract corpus has no figures (the stage is implemented for the PDF corpus)
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {a && (
        <section className="section-tight">
          <div className="container">
            <h3 style={{ fontSize: 22, marginBottom: 6 }}>End-to-end answers (Ask mode, full retrieval)</h3>
            <p className="muted" style={{ marginTop: 0 }}>Faithfulness and citation precision are judged by the Qwen3 reranker at the sentence level; answer overlap is token-level against the generated reference answer.</p>
            <div className="card" style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Question set</th>
                    <th className="num">n</th>
                    <th className="num">Refused</th>
                    <th className="num">Faithfulness</th>
                    <th className="num">Citation precision</th>
                    <th className="num">Gold passage cited</th>
                    <th className="num">Answer recall</th>
                    <th className="num">Token F1</th>
                    <th className="num">Median latency</th>
                  </tr>
                </thead>
                <tbody>
                  {(["factual", "cross", "unanswerable"] as const)
                    .filter((k) => a[k])
                    .map((k) => (
                      <tr key={k}>
                        <td>{k === "unanswerable" ? "Unanswerable (should refuse)" : k === "cross" ? "Cross-domain" : "Factual"}</td>
                        <td className="num">{a[k].n}</td>
                        <td className={`num${k === "unanswerable" ? " best" : ""}`}>{pct(a[k].refusal_rate)}</td>
                        <td className="num">{pct(a[k].faithfulness)}</td>
                        <td className="num">{pct(a[k].citation_precision)}</td>
                        <td className="num">{pct(a[k].gold_cited)}</td>
                        <td className="num">{pct(a[k].answer_recall)}</td>
                        <td className="num">{a[k].token_f1 != null ? a[k].token_f1.toFixed(3) : "—"}</td>
                        <td className="num">{a[k].median_seconds != null ? `${a[k].median_seconds.toFixed(0)} s` : "—"}</td>
                      </tr>
                    ))}
                  {small &&
                    (["factual", "unanswerable"] as const)
                      .filter((k) => small[k])
                      .map((k) => (
                        <tr key={`s-${k}`}>
                          <td className="muted">
                            {k === "factual" ? "Factual" : "Unanswerable"} · small generator ({site.models.generator_small})
                          </td>
                          <td className="num">{small[k].n}</td>
                          <td className="num">{pct(small[k].refusal_rate)}</td>
                          <td className="num">{pct(small[k].faithfulness)}</td>
                          <td className="num">{pct(small[k].citation_precision)}</td>
                          <td className="num">{pct(small[k].gold_cited)}</td>
                          <td className="num">{pct(small[k].answer_recall)}</td>
                          <td className="num">{small[k].token_f1 != null ? small[k].token_f1.toFixed(3) : "—"}</td>
                          <td className="num">{small[k].median_seconds != null ? `${small[k].median_seconds.toFixed(0)} s` : "—"}</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {an && (
        <section className="section-tight">
          <div className="container">
            <h3 style={{ fontSize: 22, marginBottom: 6 }}>Analyze tasks: water area against JRC Global Surface Water</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Each task is a natural-language request for one lake and one month. The agent plans, generates and runs the script; the result is compared with JRC GSW occurrence ≥ 50 % (1984–2021) on the same 20 m grid. Seasonal lakes are expected to deviate — that is a property of the lake, not only of the method.
            </p>
            <div className="grid-4" style={{ marginBottom: 18 }}>
              <div className="card kpi">
                <div className="v">{pct(an.success_rate)}</div>
                <div className="l">executed successfully</div>
                <div className="d">{pct(an.first_try_success_rate)} on the first attempt</div>
              </div>
              <div className="card kpi">
                <div className="v">{an.mean_repairs?.toFixed(2)}</div>
                <div className="l">self-repairs per task (mean)</div>
              </div>
              <div className="card kpi">
                <div className="v">{an.median_abs_pct_error != null ? `${an.median_abs_pct_error.toFixed(1)} %` : "—"}</div>
                <div className="l">median absolute area error</div>
                <div className="d">{pct(an.within_10pct)} of tasks within 10 %</div>
              </div>
              <div className="card kpi">
                <div className="v">{an.mean_iou?.toFixed(2) ?? "—"}</div>
                <div className="l">mean IoU with the reference mask</div>
                <div className="d">median run {an.median_seconds?.toFixed(0)} s</div>
              </div>
            </div>
            <div className="grid-2">
              <div className="card" style={{ padding: "14px 8px 4px" }}>
                <AnalyzeScatter items={an.items} />
              </div>
              <div className="card" style={{ overflow: "auto", maxHeight: 440 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Lake</th>
                      <th>Month</th>
                      <th className="num">GeoRAG km²</th>
                      <th className="num">JRC km²</th>
                      <th className="num">Error</th>
                      <th className="num">Tries</th>
                    </tr>
                  </thead>
                  <tbody>
                    {an.items.map((it: any) => (
                      <tr key={it.id}>
                        <td>{it.lake}</td>
                        <td className="mono" style={{ fontSize: 12.5 }}>{it.month}</td>
                        <td className="num">{it.water_km2 != null ? it.water_km2.toFixed(1) : "—"}</td>
                        <td className="num">{it.reference_km2 != null ? it.reference_km2.toFixed(1) : "—"}</td>
                        <td className="num">{it.abs_pct_error != null ? `${it.abs_pct_error.toFixed(1)} %` : it.ok ? "—" : "failed"}</td>
                        <td className="num">{it.attempts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="section-tight">
        <div className="container grid-2" style={{ alignItems: "start" }}>
          <div className="card" style={{ padding: 22 }}>
            <h3 style={{ fontSize: 18, marginBottom: 10 }}>Corpus</h3>
            <p className="muted" style={{ marginTop: 0, fontSize: 14 }}>
              {site.corpus.papers.toLocaleString()} papers ({site.corpus.year_range}) by first-version year, plus technical documentation, dataset descriptions and the glossary — {site.corpus.chunks.toLocaleString()} passages in total.
            </p>
            <CorpusChart site={site} />
          </div>
          <div className="card" style={{ padding: 22 }}>
            <h3 style={{ fontSize: 18, marginBottom: 10 }}>Limitations</h3>
            <ul className="muted" style={{ fontSize: 14, paddingLeft: 18, margin: 0, lineHeight: 1.7 }}>
              <li>Factual and cross-domain questions were generated by the same local model family that answers them, from the very passages used as gold; this favours lexical overlap and inflates retrieval scores relative to real user questions.</li>
              <li>The corpus is abstracts and documentation, not full text, because full-text hosts were unreachable from the build machine; claims that live in method sections are out of reach. The OpenAlex full-text path is implemented and documented.</li>
              <li>Faithfulness is judged by a 0.6B reranker, not by people; it measures whether a cited passage plausibly supports a sentence, not whether the sentence is true.</li>
              <li>The JRC reference is a 1984–2021 long-term occurrence layer, while each task is a single month; part of the area error is real seasonal and inter-annual change.</li>
              <li>Analyze success here is on single-step template tasks. Multi-step, open-ended spatial analysis — where GIS Copilot and GeoAnalystBench report the hardest failures — is not claimed.</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
