/** Architecture diagram: offline indexing (top) and query time (bottom), hand-drawn in SVG. */
export default function Architecture() {
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, accent = false) => (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={3} fill={accent ? "#e9f0f7" : "#ffffff"} stroke={accent ? "#1f5f99" : "#8a857a"} strokeWidth={accent ? 2 : 1} />
      <text x={x + 14} y={y + 26} fill="#1c1c1a" fontSize={14.5} fontWeight={700}>
        {title}
      </text>
      {sub.split("\n").map((line, i) => (
        <text key={i} x={x + 14} y={y + 46 + i * 17} fill="#4a4843" fontSize={12.5}>
          {line}
        </text>
      ))}
    </g>
  );
  const arrow = (x1: number, y1: number, x2: number, y2: number) => <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#4a4843" strokeWidth={1.3} markerEnd="url(#arr)" />;
  return (
    <figure className="arch card" style={{ padding: "18px 18px 10px", margin: 0 }}>
      <svg viewBox="0 0 1140 530" role="img" aria-label="GeoRAG architecture">
        <defs>
          <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#4a4843" />
          </marker>
        </defs>
        <text x={8} y={22} fill="#1c1c1a" fontSize={12.5} fontWeight={700} letterSpacing="0.08em">
          OFFLINE INDEXING · make index
        </text>
        {box(8, 38, 200, 112, "Open corpus", "arXiv metadata (CC0)\nOpenAlex CC BY full text\ntech docs · dataset catalogue")}
        {box(244, 38, 180, 112, "Parse & chunk", "section-aware, ~500 tokens\n15 % overlap\ntitle + section prefix")}
        {box(460, 38, 200, 52, "BM25 index", "")}
        {box(460, 98, 200, 52, "Dense vectors", "")}
        <text x={474} y={84} fill="#4a4843" fontSize={12}>bm25s · exact band & dataset ids</text>
        <text x={474} y={144} fill="#4a4843" fontSize={12}>Qwen3-Embedding-0.6B</text>
        {box(696, 38, 210, 112, "Knowledge graph", "181-term glossary, 7 entity types\nco-mention edges, NPMI\nsupporting passages per edge")}
        {box(942, 38, 190, 112, "Licence register", "manifest.parquet\nDOI · licence · URL · sha256\nno documents in git")}
        {arrow(208, 94, 242, 94)}
        {arrow(424, 70, 458, 64)}
        {arrow(424, 118, 458, 124)}
        {arrow(424, 94, 694, 94)}
        <line x1={0} y1={186} x2={1140} y2={186} stroke="#bdb7aa" strokeDasharray="4 4" />
        <text x={8} y={216} fill="#1c1c1a" fontSize={12.5} fontWeight={700} letterSpacing="0.08em">
          QUERY TIME · make serve
        </text>
        {box(8, 232, 170, 92, "Question", "chat UI or CLI\nmode: auto / manual")}
        {box(208, 232, 170, 92, "Router", "rules + LLM classifier\nAsk · Analyze · Design\nExplore")}
        {box(408, 232, 250, 92, "Hybrid retrieval", "BM25 ∪ dense ∪ graph (1–2 hops)\nreciprocal rank fusion, k = 60\nQwen3-Reranker → top 8", true)}
        {box(688, 232, 200, 92, "Local generator", "Ollama / llama.cpp\nmodel picked by VRAM tier\ncitations as [n]")}
        {box(918, 232, 214, 92, "Grounding check", "sentence ↔ cited passage\nreranker support score\nrefuse when evidence is weak")}
        {arrow(178, 278, 206, 278)}
        {arrow(378, 278, 406, 278)}
        {arrow(658, 278, 686, 278)}
        {arrow(888, 278, 916, 278)}
        {box(408, 362, 250, 112, "Analyze: plan → code → run", "typed JSON plan (AOI, months, index)\nJinja templates, no free-form code\nsandbox: rlimits, audit hooks,\nhost allow-list · ≤ 3 self-repairs")}
        {box(688, 362, 200, 112, "Sentinel-2 L2A", "Planetary Computer STAC\nor AWS sentinel-cogs\nSCL cloud mask · median\ncomposites · JRC reference")}
        {box(918, 362, 214, 112, "Outputs", "cited answer · study brief\nmap PNG + GeoTIFF + numbers\nconcept subgraph\nfull run log")}
        {arrow(533, 324, 533, 360)}
        {arrow(658, 418, 686, 418)}
        {arrow(888, 418, 916, 418)}
        {arrow(1025, 324, 1025, 360)}
        {box(8, 362, 370, 112, "Explore & Design", "Explore: entity linking → shortest paths and\nneighbours in the graph, passages on every edge\nDesign: six sections, each with its own retrieval,\ndataset links from the catalogue, references")}
        <text x={8} y={520} fill="#6f6c65" fontSize={12.5}>
          One GPU or CPU: models load per stage during indexing; at query time only the generator, the embedder and the 0.6B reranker are resident.
        </text>
      </svg>
      <figcaption className="faint" style={{ fontSize: 14, paddingTop: 6 }}>
        Figure 2. Offline indexing (top) and query-time pipeline (bottom).
      </figcaption>
    </figure>
  );
}
