import { getJSON } from "./api";
import type { GraphEdge, GraphNode } from "./types";

export interface MetricRow {
  "recall@5": number;
  "recall@10": number;
  "all@8": number;
  "mrr@10": number;
  "ndcg@10": number;
  "recall@5_ci95": [number, number];
  n: number;
}

export interface SiteData {
  generated: string;
  authors?: { name: string; github?: string | null; linkedin?: string | null }[];
  models: { generator: string; generator_small?: string | null; embedding: string; reranker: string; tier: string; hardware: string };
  corpus: { documents: number; papers: number; chunks: number; by_domain: Record<string, number>; by_source: Record<string, number>; papers_by_year: Record<string, number>; year_range: string; open_licence_papers: number };
  graph: { nodes: number; edges: number; types: Record<string, number> };
  graph_overview: { nodes: GraphNode[]; edges: GraphEdge[] };
  hero_figure?: string;
  hero_caption?: string;
  benchmark: {
    retrieval?: { n: number; configs: Record<string, { summary: { factual: MetricRow; cross?: MetricRow }; seconds: number }> };
    retrieval_paraphrased?: { n: number; configs: Record<string, { summary: { paraphrased?: MetricRow }; seconds: number }> } | null;
    answers?: Record<string, any>;
    answers_small?: Record<string, any> | null;
    analyze?: Record<string, any> & { items: any[] };
    bench_sizes?: Record<string, number>;
  };
  compute?: { stage: string; seconds: number; [k: string]: any }[];
  generation?: { tokens_per_second?: number; [k: string]: any };
}

export const loadSite = () => getJSON<SiteData>("data/site.json");

export const pct = (x: number | null | undefined, digits = 0) => (x == null ? "—" : `${(100 * x).toFixed(digits)} %`);
