import { ArrowRight, BookOpenCheck, Cpu, FlaskConical, Github, Map as MapIcon, MessageSquareText, Network, ShieldCheck } from "lucide-react";
import Architecture from "../components/Architecture";
import Constellation from "../components/Constellation";
import { asset } from "../api";
import type { DemoEntry } from "../types";
import type { SiteData } from "../site";
import { pct } from "../site";
import { RetrievalChart } from "./Benchmark";

const MODES = [
  {
    icon: MessageSquareText,
    title: "Ask",
    text: "Concise answers where every sentence carries numbered citations to the exact passages; a reranker checks each sentence against its source and flags anything unsupported.",
    example: "How does MNDWI differ from NDWI for mapping open water, and when is each preferred?",
    out: "cited answer · support score per sentence · related concepts",
    demo: "ask-water-indices",
  },
  {
    icon: MapIcon,
    title: "Analyze",
    text: "Turns a request into a typed plan, renders Python from audited templates and runs it in a sandbox against open Sentinel-2 data — with up to three self-repairs.",
    example: "Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.",
    out: "map layers · GeoTIFF · area numbers · the code itself",
    demo: "analyze-ichkeul",
  },
  {
    icon: FlaskConical,
    title: "Design",
    text: "Writes a study brief section by section, each with its own retrieval: question, area, data with access links, method, validation and risks.",
    example: "Design a study on rooftop solar potential from airborne LiDAR in a Mediterranean city.",
    out: "structured brief · dataset links · references",
    demo: "design-rooftop-solar",
  },
  {
    icon: Network,
    title: "Explore",
    text: "Links the question to the knowledge graph and draws the concepts between them; every edge opens the passages that connect the two ends.",
    example: "How are foundation models and wetlands connected in the corpus?",
    out: "interactive subgraph · concept paths · supporting passages",
    demo: "explore-foundation-wetlands",
  },
];

export default function Landing({ site, demos }: { site: SiteData | null; demos: DemoEntry[] }) {
  const c = site?.corpus;
  const full = site?.benchmark?.retrieval?.configs?.["Full: hybrid + graph + rerank"]?.summary;
  const ans = site?.benchmark?.answers;
  const an = site?.benchmark?.analyze;
  const has = (id: string) => demos.some((d) => d.id === id);

  return (
    <div className="page">
      <section className="hero">
        {site?.graph_overview && <Constellation nodes={site.graph_overview.nodes} edges={site.graph_overview.edges} />}
        <div className="container hero-inner">
          <div>
            <div className="eyebrow">Local · open-weight · grounded</div>
            <h1 style={{ marginTop: 14 }}>
              GeoRAG <span className="grad">Copilot</span>
            </h1>
            <p className="sub">
              A graph-and-vector retrieval-augmented agent that turns geospatial literature into executable Earth-observation workflows — cited answers, Sentinel-2 analyses that actually run, study designs and a knowledge graph across five research fields.
            </p>
            <div className="hero-actions">
              <a className="btn primary" href="#/copilot">
                Open the copilot <ArrowRight size={16} />
              </a>
              <a className="btn" href="#/benchmark">
                See the benchmark
              </a>
              <a className="btn" href="https://github.com/emna-saada/GeoRAG" target="_blank" rel="noreferrer">
                <Github size={16} /> Source
              </a>
            </div>
            <div className="hero-badges">
              {["Qwen3-Embedding", "Qwen3-Reranker", "BM25 + RRF", "Knowledge graph", "Sentinel-2 L2A", "Sandboxed code", "FastAPI · React · MapLibre"].map((b) => (
                <span key={b} className="badge">
                  {b}
                </span>
              ))}
            </div>
          </div>
          <div className="card hero-preview">
            <div className="preview-q">
              <div className="avatar user">You</div>
              <div>Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.</div>
            </div>
            {site?.hero_figure ? (
              <figure className="figure" style={{ margin: 0 }}>
                <img src={asset(site.hero_figure)} alt="Water extent change at Lake Ichkeul" />
                <figcaption>{site.hero_caption}</figcaption>
              </figure>
            ) : (
              <div className="placeholder" style={{ height: 260 }}>Run `georag demos` to generate the showcase.</div>
            )}
          </div>
        </div>
      </section>

      <section className="section-tight">
        <div className="container">
          <div className="stats">
            <div className="stat">
              <div className="v">{c ? c.papers.toLocaleString() : "—"}</div>
              <div className="l">research papers across 5 domains, {c?.year_range}</div>
            </div>
            <div className="stat">
              <div className="v">{c ? c.chunks.toLocaleString() : "—"}</div>
              <div className="l">indexed passages · docs · dataset entries</div>
            </div>
            <div className="stat">
              <div className="v">{site?.graph ? site.graph.nodes : "—"}<small> / {site?.graph ? site.graph.edges.toLocaleString() : "—"}</small></div>
              <div className="l">graph concepts / links</div>
            </div>
            <div className="stat">
              <div className="v">{full ? pct(full.factual["recall@5"]) : "—"}</div>
              <div className="l">Recall@5 on {full?.factual.n ?? "—"} benchmark questions</div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">Four generative modes</div>
          <h2 className="title">From a question to a cited answer, a map or a study plan</h2>
          <p className="lead">Every mode is grounded in retrieved sources and runs on local hardware. Click a card to replay a recorded run in the copilot.</p>
          <div className="grid-2" style={{ marginTop: 36 }}>
            {MODES.map((m) => (
              <a key={m.title} className="card mode-card" href={has(m.demo) ? `#/copilot?demo=${m.demo}` : "#/copilot"} style={{ color: "inherit", textDecoration: "none" }}>
                <div className="icon">
                  <m.icon size={20} />
                </div>
                <h3>{m.title}</h3>
                <p>{m.text}</p>
                <div className="example">“{m.example}”</div>
                <div className="out">→ {m.out}</div>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 20 }}>
        <div className="container">
          <div className="eyebrow">How it works</div>
          <h2 className="title">Three retrieval paths, one reranker, a sandbox</h2>
          <p className="lead">
            Sparse BM25 keeps exact identifiers (B11, EPSG:32632, Sen1Floods11); dense Qwen3 embeddings catch paraphrase; the knowledge graph pulls in passages about neighbouring concepts. Reciprocal rank fusion merges them and a cross-encoder reranks the strongest candidates.
          </p>
          <div style={{ marginTop: 32 }}>
            <Architecture />
          </div>
        </div>
      </section>

      {site?.benchmark?.retrieval && (
        <section className="section" style={{ paddingTop: 20 }}>
          <div className="container">
            <div className="eyebrow">GeoRAG-Bench</div>
            <h2 className="title">What each component buys</h2>
            <p className="lead">
              Retrieval ablation on {full?.factual.n} factual questions — as generated from their passages and reworded — and {full?.cross?.n} cross-domain questions that need two passages from different fields. Same corpus, same questions; only the retrieval components change.
            </p>
            <div className="card" style={{ marginTop: 28, padding: "18px 12px 8px" }}>
              <RetrievalChart site={site} metric="recall@5" />
            </div>
            <div className="grid-4" style={{ marginTop: 18 }}>
              {ans?.factual && (
                <div className="card kpi">
                  <div className="v">{pct(ans.factual.faithfulness)}</div>
                  <div className="l">sentences supported by their citation</div>
                </div>
              )}
              {ans?.unanswerable && (
                <div className="card kpi">
                  <div className="v">{pct(ans.unanswerable.refusal_rate)}</div>
                  <div className="l">out-of-scope questions correctly refused</div>
                </div>
              )}
              {an && (
                <div className="card kpi">
                  <div className="v">{pct(an.success_rate)}</div>
                  <div className="l">Analyze tasks executed ({an.n} lakes × months)</div>
                </div>
              )}
              {an?.median_abs_pct_error != null && (
                <div className="card kpi">
                  <div className="v">{an.median_abs_pct_error.toFixed(1)} %</div>
                  <div className="l">median water-area error vs JRC GSW</div>
                </div>
              )}
            </div>
            <div style={{ marginTop: 22 }}>
              <a className="btn" href="#/benchmark">
                Full results and limitations <ArrowRight size={15} />
              </a>
            </div>
          </div>
        </section>
      )}

      <section className="section" style={{ paddingTop: 20 }}>
        <div className="container grid-3">
          <div className="card" style={{ padding: 24 }}>
            <ShieldCheck color="var(--accent)" />
            <h3 style={{ margin: "12px 0 8px", fontSize: 18 }}>Trustworthy by construction</h3>
            <p className="muted" style={{ margin: 0, fontSize: 14.5 }}>
              Refuses when retrieval finds nothing relevant. Citation numbers can only point at retrieved passages. Generated code is template-based, statically checked and run with resource limits, audit hooks and a host allow-list.
            </p>
          </div>
          <div className="card" style={{ padding: 24 }}>
            <BookOpenCheck color="var(--accent)" />
            <h3 style={{ margin: "12px 0 8px", fontSize: 18 }}>Legally clean corpus</h3>
            <p className="muted" style={{ margin: 0, fontSize: 14.5 }}>
              Only openly licensed sources. The repository stores identifiers, licences and checksums — never the documents — so anyone can rebuild and verify the same index. <a href="#/sources">Browse the sources</a>.
            </p>
          </div>
          <div className="card" style={{ padding: 24 }}>
            <Cpu color="var(--accent)" />
            <h3 style={{ margin: "12px 0 8px", fontSize: 18 }}>Runs on one machine</h3>
            <p className="muted" style={{ margin: 0, fontSize: 14.5 }}>
              Detects the GPU and picks a model tier automatically, from a CPU-only laptop to a 24 GB card. Models load one stage at a time; nothing leaves the machine except open-data downloads.
            </p>
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 20 }}>
        <div className="container grid-2" style={{ alignItems: "start" }}>
          <div>
            <div className="eyebrow">Run it yourself</div>
            <h2 className="title">Clone, index, serve</h2>
            <p className="lead" style={{ fontSize: 16 }}>Python 3.11+, Node 20 and, optionally, Ollama with a GPU. Without a GPU the CPU tier serves a 4B model through llama.cpp.</p>
          </div>
          <div className="terminal">
            <div><span className="p">$</span> git clone https://github.com/emna-saada/GeoRAG && cd GeoRAG</div>
            <div><span className="p">$</span> make setup <span className="c"># uv env, npm deps, hardware tier</span></div>
            <div><span className="p">$</span> make index <span className="c"># corpus, chunks, BM25, vectors, graph</span></div>
            <div><span className="p">$</span> make eval <span className="c"># GeoRAG-Bench → results/</span></div>
            <div><span className="p">$</span> make serve <span className="c"># http://127.0.0.1:8000</span></div>
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="container">
          <div className="grid-2">
            {(site?.authors ?? [
              { name: "Emna Saada", github: "https://github.com/emna-saada" },
              { name: "Souhe Hamdani", github: null },
            ]).map((a) => (
              <div className="card author" key={a.name}>
                <div className="pic">
                  {a.name
                    .split(" ")
                    .map((w) => w[0])
                    .join("")}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 17 }}>{a.name}</div>
                  <div className="muted" style={{ fontSize: 14.5 }}>Geospatial data science — GIS, remote sensing, LiDAR, digital twins and computer vision.</div>
                  <div style={{ display: "flex", gap: 14, marginTop: 6, fontSize: 14 }}>
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
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
