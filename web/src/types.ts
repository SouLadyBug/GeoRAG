export type Mode = "ask" | "analyze" | "design" | "explore";

export interface Chunk {
  chunk_id: string;
  doc_id: string;
  title: string;
  section: string;
  text: string;
  domain: string;
  year: number | null;
  url: string | null;
}

export interface Passage {
  chunk: Chunk;
  score: number;
  sources: Record<string, number>;
  rerank_score: number | null;
  entities: string[];
}

export interface Citation {
  n: number;
  chunk_id: string;
  doc_id: string;
  title: string;
  url: string | null;
  year: number | null;
  section: string;
  quote: string;
}

export interface Sentence {
  text: string;
  citations: number[];
  support: number | null;
  supported: boolean;
}

export interface AskResult {
  mode: "ask";
  question: string;
  answer: string;
  sentences: Sentence[];
  citations: Citation[];
  refused: boolean;
  refusal_reason: string | null;
  related: string[];
  faithfulness: number | null;
  passages: Passage[];
  timings: Record<string, number>;
}

export interface DesignSection {
  key: string;
  heading: string;
  markdown: string;
  citations: number[];
  supported_ratio: number | null;
}

export interface DesignResult {
  mode: "design";
  question: string;
  title: string;
  sections: DesignSection[];
  citations: Citation[];
  datasets: { title: string; url: string; chunk_id: string }[];
  markdown: string;
  faithfulness: number | null;
  timings: Record<string, number>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  degree: number;
  seed?: boolean;
  definition?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  chunks?: string[];
}

export interface ExploreResult {
  mode: "explore";
  question: string;
  seeds: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  paths: string[][];
  summary: string;
  citations: Citation[];
  passages: Record<string, Citation>;
  timings: Record<string, number>;
}

export interface AnalysisPlan {
  task: "water_change" | "water_extent" | "ndvi";
  place: string;
  bbox: [number, number, number, number] | null;
  periods: string[];
  index: string;
  threshold: number;
  max_cloud: number;
  max_scenes: number;
  resolution: number;
  rationale: string;
}

export interface Attempt {
  n: number;
  plan: AnalysisPlan;
  code: string;
  ok: boolean;
  seconds: number;
  stdout: string;
  stderr: string;
  error: string | null;
}

export interface LayerSet {
  bounds: [number, number, number, number];
  layers: Record<string, string>;
}

export interface AnalyzeResult {
  mode: "analyze";
  question: string;
  plan: AnalysisPlan;
  code: string;
  attempts: Attempt[];
  ok: boolean;
  run_id: string;
  outputs: Record<string, string>;
  numbers: Record<string, any>;
  citations: Citation[];
  explanation: string;
  timings: Record<string, number>;
}

export type Result = AskResult | DesignResult | ExploreResult | AnalyzeResult;

export interface StreamEvent {
  type: string;
  [key: string]: any;
}

export interface Toggles {
  bm25: boolean;
  dense: boolean;
  graph: boolean;
  rerank: boolean;
  figures: boolean;
}

export interface DemoEntry {
  id: string;
  mode: Mode;
  question: string;
  title: string;
  blurb: string;
}

export interface Turn {
  id: string;
  question: string;
  mode: Mode | null;
  events: StreamEvent[];
  streamed: string;
  result: Result | null;
  error: string | null;
  done: boolean;
  assetBase: string; // where analyze outputs are served from
}
