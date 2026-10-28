import type { DemoEntry, Mode, StreamEvent, Toggles } from "./types";

export const BASE = import.meta.env.BASE_URL;
export const asset = (path: string) => `${BASE}${path.replace(/^\//, "")}`;

export interface Health {
  version: string;
  tier: string;
  llm: { model: string; available: boolean };
  embedding: string;
  reranker: string;
  corpus: Record<string, any> | null;
}

export async function detectBackend(): Promise<Health | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 1500);
  try {
    const r = await fetch("/api/health", { signal: ctrl.signal });
    if (!r.ok) return null;
    const ct = r.headers.get("content-type") || "";
    return ct.includes("json") ? ((await r.json()) as Health) : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(asset(path));
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return (await r.json()) as T;
}

/** Stream a live query from the FastAPI backend (Server-Sent Events over a POST). */
export async function runLive(
  question: string,
  mode: Mode | "auto",
  toggles: Toggles,
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const r = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, mode, toggles }),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`query failed: ${r.status}`);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.search(/\r?\n\r?\n/)) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx).replace(/^\r?\n\r?\n/, "");
      const data = block
        .split(/\r?\n/)
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(JSON.parse(data));
    }
  }
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("aborted", "AbortError"));
    });
  });

/** Replay a recorded run with its original event order, at a readable pace. */
export async function replayDemo(id: string, onEvent: (e: StreamEvent) => void, signal: AbortSignal): Promise<void> {
  const rec = await getJSON<{ events: StreamEvent[]; result: any }>(`demo/${id}/run.json`);
  for (const e of rec.events) {
    if (signal.aborted) return;
    const pause = e.type === "token" ? 14 : e.type === "section" ? 380 : e.type === "attempt" ? 700 : 260;
    await sleep(pause, signal);
    onEvent(e);
  }
  await sleep(200, signal);
  onEvent({ type: "result", result: rec.result });
}

export async function loadDemos(): Promise<DemoEntry[]> {
  try {
    return await getJSON<DemoEntry[]>("demo/index.json");
  } catch {
    return [];
  }
}
