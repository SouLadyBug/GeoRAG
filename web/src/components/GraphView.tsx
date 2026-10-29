import cytoscape, { type Core } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import type { Citation, GraphEdge, GraphNode } from "../types";

export const TYPE_COLORS: Record<string, string> = {
  method: "#a78bfa",
  sensor: "#38bdf8",
  dataset: "#f59e0b",
  product: "#34d399",
  application: "#fb7185",
  place: "#facc15",
  standard: "#94a3b8",
};

const TYPE_LABEL: Record<string, string> = {
  method: "Method",
  sensor: "Sensor / platform",
  dataset: "Dataset",
  product: "Index / product",
  application: "Application",
  place: "Place",
  standard: "Standard / software",
};

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  paths?: string[][];
  passages?: Record<string, Citation>;
  compact?: boolean;
  maxLinks?: number;
}

export default function GraphView({ nodes, edges, paths = [], passages = {}, compact, maxLinks = 3 }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const [picked, setPicked] = useState<{ kind: "edge" | "node"; data: any } | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const onPath = new Set<string>();
    for (const p of paths) for (let i = 0; i < p.length - 1; i++) onPath.add([p[i], p[i + 1]].sort().join("|"));
    // Keep every path edge plus each concept's strongest links; the full co-mention graph is a hairball.
    const keep = new Set<string>();
    const byNode = new Map<string, GraphEdge[]>();
    for (const e of edges) {
      for (const n of [e.source, e.target]) byNode.set(n, [...(byNode.get(n) ?? []), e]);
      if (onPath.has([e.source, e.target].sort().join("|"))) keep.add(`${e.source}__${e.target}`);
    }
    for (const list of byNode.values()) list.sort((a, b) => b.weight - a.weight).slice(0, maxLinks).forEach((e) => keep.add(`${e.source}__${e.target}`));
    const shown = edges.filter((e) => keep.has(`${e.source}__${e.target}`));
    const maxDeg = Math.max(1, ...nodes.map((n) => n.degree));
    const inst = cytoscape({
      container: el.current,
      elements: [
        ...nodes.map((n) => ({
          data: { id: n.id, label: n.label, type: n.type, size: 18 + 34 * Math.sqrt(n.degree / maxDeg), seed: n.seed ? 1 : 0, definition: n.definition, degree: n.degree },
        })),
        ...shown.map((e) => ({
          data: { id: `${e.source}__${e.target}`, source: e.source, target: e.target, weight: e.weight, chunks: e.chunks ?? [], path: onPath.has([e.source, e.target].sort().join("|")) ? 1 : 0 },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: any) => TYPE_COLORS[ele.data("type")] ?? "#94a3b8",
            width: "data(size)",
            height: "data(size)",
            label: "data(label)",
            color: "#e2e8f0",
            "font-size": compact ? 9 : 11,
            "font-family": "Inter Variable, Inter, sans-serif",
            "font-weight": 600,
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-outline-color": "#060a13",
            "text-outline-width": 2.5,
            "border-width": 0,
            "background-opacity": 0.92,
          } as any,
        },
        { selector: "node[seed = 1]", style: { "border-width": 3, "border-color": "#ffffff", "font-size": compact ? 11 : 13, "z-index": 10 } as any },
        {
          selector: "edge",
          style: { width: (ele: any) => 0.6 + 4 * ele.data("weight"), "line-color": "#334155", opacity: 0.7, "curve-style": "haystack" } as any,
        },
        { selector: "edge[path = 1]", style: { "line-color": "#2dd4bf", opacity: 1, "z-index": 5 } as any },
        { selector: ":selected", style: { "border-width": 3, "border-color": "#2dd4bf", "line-color": "#5eead4" } as any },
        { selector: ".faded", style: { opacity: 0.12 } },
      ],
      layout: { name: "cose", animate: false, nodeRepulsion: () => 26000, idealEdgeLength: () => 110, nodeOverlap: 24, gravity: 0.25, numIter: 2500, padding: 36 } as any,
      wheelSensitivity: 0.25,
      minZoom: 0.3,
      maxZoom: 3,
    });
    inst.on("tap", "edge", (evt) => {
      const d = evt.target.data();
      setPicked({ kind: "edge", data: { ...d, sourceLabel: inst.getElementById(d.source).data("label"), targetLabel: inst.getElementById(d.target).data("label") } });
    });
    inst.on("tap", "node", (evt) => {
      const n = evt.target;
      inst.elements().addClass("faded");
      n.closedNeighborhood().removeClass("faded");
      setPicked({ kind: "node", data: n.data() });
    });
    inst.on("tap", (evt) => {
      if (evt.target === inst) {
        inst.elements().removeClass("faded");
        setPicked(null);
      }
    });
    cy.current = inst;
    // The panel may be hidden behind a tab when the graph is built: lay out again once it has a size.
    let laidOut = (el.current?.clientWidth ?? 0) > 0;
    const ro = new ResizeObserver(() => {
      inst.resize();
      if (!laidOut && (el.current?.clientWidth ?? 0) > 0) {
        laidOut = true;
        inst.layout({ name: "cose", animate: false, nodeRepulsion: () => 26000, idealEdgeLength: () => 110, nodeOverlap: 24, gravity: 0.25, numIter: 2500, padding: 36 } as any).run();
      }
      inst.fit(undefined, 36);
    });
    if (el.current) ro.observe(el.current);
    return () => {
      ro.disconnect();
      inst.destroy();
    };
  }, [nodes, edges, paths, compact, maxLinks]);

  const types = Array.from(new Set(nodes.map((n) => n.type)));

  return (
    <div className="graph-wrap">
      <div ref={el} style={{ position: "absolute", inset: 0 }} />
      {!compact && (
        <div className="graph-legend card">
          {types.map((t) => (
            <div key={t}>
              <i style={{ background: TYPE_COLORS[t] }} />
              {TYPE_LABEL[t] ?? t}
            </div>
          ))}
          <div style={{ marginTop: 6 }} className="faint">
            Click an edge for the passages behind it
          </div>
        </div>
      )}
      {picked && !compact && (
        <div className="edge-card card">
          {picked.kind === "edge" ? (
            <>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>
                {picked.data.sourceLabel} ↔ {picked.data.targetLabel}
              </div>
              <div className="faint" style={{ fontSize: 12, marginBottom: 10 }}>
                NPMI {picked.data.weight.toFixed(2)} · {picked.data.chunks.length} supporting passages shown
              </div>
              {(picked.data.chunks as string[]).map((cid) => {
                const c = passages[cid];
                if (!c) return null;
                return (
                  <div key={cid} className="src" style={{ gridTemplateColumns: "1fr", marginBottom: 6 }}>
                    <div>
                      <div className="t">{c.title}</div>
                      <div className="s">
                        {c.year ?? ""} {c.url && <a href={c.url} target="_blank" rel="noreferrer">source ↗</a>}
                      </div>
                      <div className="quote">{c.quote}</div>
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                <span className="chip">
                  <span className="sw" style={{ background: TYPE_COLORS[picked.data.type] }} />
                  {TYPE_LABEL[picked.data.type] ?? picked.data.type}
                </span>
                <span className="faint" style={{ fontSize: 12 }}>
                  {picked.data.degree} mentions
                </span>
              </div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{picked.data.label}</div>
              {picked.data.definition && <div className="muted" style={{ fontSize: 13.5, marginTop: 6 }}>{picked.data.definition}</div>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
