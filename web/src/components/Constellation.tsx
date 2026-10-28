import { useEffect, useRef } from "react";
import type { GraphEdge, GraphNode } from "../types";
import { TYPE_COLORS } from "./GraphView";

/** Slowly drifting rendering of the real knowledge graph, used as the hero background. */
export default function Constellation({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !nodes.length) return;
    const ctx = canvas.getContext("2d")!;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    let w = 0;
    let h = 0;
    const resize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const rnd = (i: number) => {
      const x = Math.sin(i * 12.9898) * 43758.5453;
      return x - Math.floor(x);
    };
    const maxDeg = Math.max(...nodes.map((n) => n.degree));
    const pts = nodes.map((n, i) => ({
      ...n,
      x: 0.45 + 0.55 * rnd(i + 1),
      y: 0.05 + 0.9 * rnd(i + 101),
      vx: (rnd(i + 7) - 0.5) * 0.00012,
      vy: (rnd(i + 13) - 0.5) * 0.00012,
      r: 1.5 + 4.5 * Math.sqrt(n.degree / maxDeg),
    }));
    const idx = new Map(pts.map((p, i) => [p.id, i]));
    const links = edges.map((e) => [idx.get(e.source), idx.get(e.target), e.weight] as const).filter(([a, b]) => a != null && b != null);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of pts) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0.4 || p.x > 1) p.vx *= -1;
        if (p.y < 0.02 || p.y > 0.98) p.vy *= -1;
      }
      for (const [a, b, wgt] of links) {
        const p = pts[a as number];
        const q = pts[b as number];
        ctx.strokeStyle = `rgba(94, 234, 212, ${0.05 + 0.18 * (wgt as number)})`;
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(p.x * w, p.y * h);
        ctx.lineTo(q.x * w, q.y * h);
        ctx.stroke();
      }
      for (const p of pts) {
        ctx.fillStyle = TYPE_COLORS[p.type] ?? "#94a3b8";
        ctx.globalAlpha = 0.75;
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, p.r, 0, Math.PI * 2);
        ctx.fill();
        if (p.r > 4.2) {
          ctx.globalAlpha = 0.55;
          ctx.fillStyle = "#cbd5e1";
          ctx.font = "500 11px Inter, sans-serif";
          ctx.fillText(p.label, p.x * w + p.r + 4, p.y * h + 4);
        }
        ctx.globalAlpha = 1;
      }
      if (!reduce) raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [nodes, edges]);
  return <canvas ref={ref} className="constellation" />;
}
