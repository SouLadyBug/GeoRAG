import { ArrowRight, BookOpenCheck, Cpu, FlaskConical, Github, Map as MapIcon, MessageSquareText, Network, ShieldCheck } from "lucide-react";
import { asset } from "../api";
import Architecture from "../components/Architecture";
import type { SiteData } from "../site";
import { pct } from "../site";
import type { DemoEntry } from "../types";
import { RetrievalChart } from "./Benchmark";

const MODES = [
  {
    icon: MessageSquareText,
    title: "Ask",
    text: "Short answers in which every sentence cites the passage it comes from. A cross-encoder checks each sentence against its source and marks anything the source does not support.",
    example: "How does MNDWI differ from NDWI for mapping open water, and when is each preferred?",
    out: "cited answer, support score per sentence, related concepts",
    demo: "ask-water-indices",
  },
  {
    icon: MapIcon,
    title: "Analyze",
    text: "Turns a request into a typed plan, fills an audited Python template and runs it in a sandbox on open Sentinel-2 data, repairing the plan up to three times if a run fails.",
    example: "Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.",
    out: "map layers, GeoTIFFs, areas and the script itself",
    demo: "analyze-ichkeul",
  },
  {
    icon: FlaskConical,
    title: "Design",
    text: "Writes a study brief one section at a time — question, study area, data with access links, method, validation, risks — each section with its own retrieval.",
    example: "Design a study on rooftop solar potential from airborne LiDAR in a Mediterranean city.",
    out: "six-section brief with references",
    demo: "design-rooftop-solar",
  },
  {
    icon: Network,
    title: "Explore",
    text: "Finds the concepts named in a question in the knowledge graph and draws the paths between them. Every link opens the passages that connect its two ends.",
    example: "How are foundation models and wetlands connected in the corpus?",
    out: "interactive subgraph with supporting passages",
    demo: "explore-foundation-wetlands",
  },
];

export default function Landing({ site, demos }: { site: SiteData | null; demos: DemoEntry[] }) {
  const c = site?.corpus;
  const full = site?.benchmark?.retrieval?.configs?.["Full: hybrid + graph + rerank"]?.summary;
  const ans = site?.benchmark?.answers;
  const an = site?.benchmark?.analyze;
  const has = (id: string) => demos.some((d) => d.id === id);
  const authors = site?.authors ?? [
    { name: "Emna Saada", github: "https://github.com/emna-saada" },
    { name: "Souhe Hamdani", github: null },
  ];

  return (
    <main className="page">
      <section className="hero">
        <div className="container hero-inner">
          <div>
            <div className="eyebrow">Open research software</div>
            <h1 style={{ marginTop: 10 }}>
              GeoRAG Copilot
              <span>A local assistant that turns geospatial literature into Earth-observation analyses that actually run.</span>
            </h1>
            <p className="sub">
              Ask a question and get an answer with citations; ask for a map and get Sentinel-2 code, executed, with the result. Built on open-weight models and an openly licensed corpus covering GIS, remote sensing, LiDAR, digital twins and geospatial computer vision.
            </p>
            <div className="hero-actions">
              <a className="btn primary" href="#/copilot">
                Open the copilot <ArrowRight size={16} aria-hidden="true" />
              </a>
              <a className="btn" href="#/benchmark">
                Read the results
              </a>
              <a className="btn" href="https://github.com/emna-saada/GeoRAG" target="_blank" rel="noreferrer">
                <Github size={16} aria-hidden="true" /> Source code
              </a>
            </div>
          </div>
          <div className="hero-badges" aria-label="Main components">
            <span className="h">Built with</span>
            {["Qwen3 embedding and reranker", "BM25 + reciprocal rank fusion", "Knowledge graph (181 concepts)", "Sentinel-2 L2A via STAC / AWS", "Sandboxed Python", "FastAPI · React · MapLibre"].map((b) => (
              <span key={b}>{b}</span>
            ))}
          </div>
          {site?.hero_figure ? (
            <figure className="hero-preview hero-figure">
              <img src={asset(site.hero_figure)} alt="Open water at Lake Ichkeul, Tunisia, in February 2020 and February 2025, with the change between the two months" />
              <figcaption>
                <b>Figure 1.</b> Output of the request “Map MNDWI water extent at Ichkeul for February 2020 vs February 2025”. {site.hero_caption}
              </figcaption>
            </figure>
          ) : (
            <div className="placeholder card hero-figure" style={{ height: 280 }}>
              Run <code>georag demos</code> to generate the showcase.
            </div>
          )}
        </div>
      </section>

      <section className="section-tight" style={{ background: "var(--paper)" }} aria-label="Key figures">
        <div className="container">
          <div className="stats">
            <div className="stat">
              <div className="v">{c ? c.papers.toLocaleString() : "—"}</div>
              <div className="l">papers across five fields, {c?.year_range}</div>
            </div>
            <div className="stat">
              <div className="v">{c ? c.chunks.toLocaleString() : "—"}</div>
              <div className="l">indexed passages, documentation and dataset entries</div>
            </div>
            <div className="stat">
              <div className="v">
                {site?.graph ? site.graph.nodes : "—"}
                <small> / {site?.graph ? site.graph.edges.toLocaleString() : "—"}</small>
              </div>
              <div className="l">concepts / links in the knowledge graph</div>
            </div>
            <div className="stat">
              <div className="v">{an?.median_abs_pct_error != null ? `${an.median_abs_pct_error.toFixed(1)} %` : "—"}</div>
              <div className="l">median water-area error against JRC Global Surface Water, {an?.n ?? "—"} tasks</div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">What it does</div>
          <h2 className="title">Four ways to use the literature</h2>
          <p className="lead">Each mode works from retrieved sources and runs on your own machine. Open a card to replay a recorded run.</p>
          <div className="grid-2" style={{ marginTop: 28 }}>
            {MODES.map((m) => (
              <a key={m.title} className="card mode-card" href={has(m.demo) ? `#/copilot?demo=${m.demo}` : "#/copilot"}>
                <div className="icon">
                  <m.icon size={20} aria-hidden="true" />
                </div>
                <h3>{m.title}</h3>
                <p>{m.text}</p>
                <div className="example">“{m.example}”</div>
                <div className="out">{m.out}</div>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">How it works</div>
          <h2 className="title">Three ways to find a passage, one judge, one sandbox</h2>
          <p className="lead">
            BM25 keeps exact identifiers such as B11, EPSG:32632 or Sen1Floods11. Dense Qwen3 embeddings catch paraphrase. The knowledge graph brings in passages about neighbouring concepts. Reciprocal rank fusion merges the three lists and a cross-encoder reranks the best candidates.
          </p>
          <div style={{ marginTop: 28 }}>
            <Architecture />
          </div>
        </div>
      </section>

      {site?.benchmark?.retrieval && (
        <section className="section">
          <div className="container">
            <div className="eyebrow">Evaluation</div>
            <h2 className="title">What each component adds</h2>
            <p className="lead">
              Recall@5 on {full?.factual.n} factual questions, as generated and reworded, and on {full?.cross?.n} cross-domain questions that need two passages from different fields. Same corpus and questions throughout; only the retrieval components change.
            </p>
            <div className="card" style={{ marginTop: 24, padding: "16px 8px 4px" }}>
              <RetrievalChart site={site} metric="recall@5" />
            </div>
            <div className="grid-4" style={{ marginTop: 16 }}>
              {ans?.factual && (
                <div className="card kpi">
                  <div className="v">{pct(ans.factual.faithfulness)}</div>
                  <div className="l">of answer sentences supported by the passage they cite</div>
                </div>
              )}
              {ans?.unanswerable && (
                <div className="card kpi">
                  <div className="v">{pct(ans.unanswerable.refusal_rate)}</div>
                  <div className="l">of out-of-scope questions refused</div>
                </div>
              )}
              {an && (
                <div className="card kpi">
                  <div className="v">
                    {Math.round(an.first_try_success_rate * an.n)} / {an.n}
                  </div>
                  <div className="l">Analyze tasks executed on the first attempt</div>
                </div>
              )}
              {an?.mean_iou != null && (
                <div className="card kpi">
                  <div className="v">{an.mean_iou.toFixed(2)}</div>
                  <div className="l">mean IoU of water masks with the JRC reference</div>
                </div>
              )}
            </div>
            <p style={{ marginTop: 18 }}>
              <a href="#/benchmark">Full results, method and limitations →</a>
            </p>
          </div>
        </section>
      )}

      <section className="section">
        <div className="container grid-3">
          <div className="principle">
            <ShieldCheck className="icon" aria-hidden="true" />
            <h3>Grounded or silent</h3>
            <p>
              The assistant declines when retrieval finds nothing relevant. Citation numbers can only point at retrieved passages. Generated code comes from templates, passes a static check and runs with resource limits, audit hooks and a host allow-list.
            </p>
          </div>
          <div className="principle">
            <BookOpenCheck className="icon" aria-hidden="true" />
            <h3>Openly licensed corpus</h3>
            <p>
              The repository stores identifiers, licences and checksums, never the documents, so anyone can rebuild and verify the same index. <a href="#/sources">Browse the sources</a>.
            </p>
          </div>
          <div className="principle">
            <Cpu className="icon" aria-hidden="true" />
            <h3>One machine</h3>
            <p>
              The GPU is detected and a model size chosen automatically, from a laptop CPU to a 24 GB card. Nothing leaves the machine except downloads of open data.
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container grid-2" style={{ alignItems: "start" }}>
          <div>
            <div className="eyebrow">Run it yourself</div>
            <h2 className="title">Clone, index, serve</h2>
            <p className="lead" style={{ fontSize: 16.5 }}>
              Needs Python 3.11+, Node 20 and, optionally, Ollama with a GPU. Without a GPU, a 4-billion-parameter model is served through llama.cpp.
            </p>
          </div>
          <div className="terminal" aria-label="Commands">
            <div>
              <span className="p">$ </span>git clone https://github.com/emna-saada/GeoRAG && cd GeoRAG
            </div>
            <div>
              <span className="p">$ </span>make setup <span className="c"># environment, web dependencies, hardware tier</span>
            </div>
            <div>
              <span className="p">$ </span>make index <span className="c"># corpus, chunks, BM25, vectors, graph</span>
            </div>
            <div>
              <span className="p">$ </span>make eval <span className="c"># GeoRAG-Bench → results/</span>
            </div>
            <div>
              <span className="p">$ </span>make serve <span className="c"># http://127.0.0.1:8000</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section" aria-label="Authors">
        <div className="container">
          <div className="eyebrow" style={{ marginBottom: 14 }}>
            Authors
          </div>
          <div className="grid-2">
            {authors.map((a) => (
              <div className="card author" key={a.name}>
                <div className="pic" aria-hidden="true">
                  {a.name
                    .split(" ")
                    .map((w) => w[0])
                    .join("")}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 17 }}>{a.name}</div>
                  <div className="muted" style={{ fontSize: 15 }}>
                    Geospatial data science: GIS, remote sensing, LiDAR, digital twins and computer vision.
                  </div>
                  {(a.github || a.linkedin) && (
                    <div style={{ display: "flex", gap: 14, marginTop: 4, fontSize: 15 }}>
                      {a.github && (
                        <a href={a.github} target="_blank" rel="noreferrer">
                          GitHub
                        </a>
                      )}
                      {a.linkedin && (
                        <a href={a.linkedin} target="_blank" rel="noreferrer">
                          LinkedIn
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
