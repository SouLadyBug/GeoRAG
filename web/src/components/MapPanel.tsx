import maplibregl, { type Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type { AnalyzeResult, LayerSet } from "../types";

const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: ["https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png", "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors © CARTO",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#05080f" } },
    { id: "carto", type: "raster", source: "carto", paint: { "raster-opacity": 0.9 } },
  ],
};

type LayerKey = { id: string; label: string; file: string; bounds: [number, number, number, number] };

function corners(b: [number, number, number, number]): [[number, number], [number, number], [number, number], [number, number]] {
  const [w, s, e, n] = b;
  return [
    [w, n],
    [e, n],
    [e, s],
    [w, s],
  ];
}

function layersOf(result: AnalyzeResult): { base: LayerKey[]; overlays: LayerKey[]; periods: string[] } {
  const raw = result.outputs.layers ? (JSON.parse(result.outputs.layers) as Record<string, any>) : {};
  const sets: { tag: string; set: LayerSet }[] = raw.layers ? [{ tag: result.plan.periods[0], set: raw as LayerSet }] : Object.entries(raw).map(([k, v], i) => ({ tag: result.plan.periods[i] ?? k, set: v as LayerSet }));
  const base: LayerKey[] = [];
  const overlays: LayerKey[] = [];
  for (const { tag, set } of sets) {
    for (const [name, file] of Object.entries(set.layers)) {
      const entry = { id: `${tag}-${name}`, label: name === "truecolor" ? `True colour ${tag}` : name === "water" ? `Water ${tag}` : name === "ndvi" ? `NDVI ${tag}` : "Change", file, bounds: set.bounds };
      (name === "truecolor" ? base : overlays).push(entry);
    }
  }
  return { base, overlays, periods: sets.map((s) => s.tag) };
}

export default function MapPanel({ result, assetBase }: { result: AnalyzeResult | null; assetBase: string }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const { base, overlays, periods } = useMemo(() => (result ? layersOf(result) : { base: [], overlays: [], periods: [] }), [result]);
  const [period, setPeriod] = useState(0);
  const [overlay, setOverlay] = useState<string | null>(null);
  const [opacity, setOpacity] = useState(0.85);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = new maplibregl.Map({ container: el.current, style: STYLE, center: [9.65, 37.15], zoom: 9, attributionControl: { compact: true } });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => setReady(true));
    map.current = m;
    // The panel starts hidden behind a tab; resize the canvas whenever it becomes visible.
    const ro = new ResizeObserver(() => m.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!result) return;
    const change = overlays.find((o) => o.label === "Change");
    setOverlay(change ? change.id : overlays[0]?.id ?? null);
    setPeriod(periods.length > 1 ? periods.length - 1 : 0);
  }, [result, overlays, periods]);

  // Add every layer once per result; visibility is switched afterwards.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !result) return;
    const all = [...base, ...overlays];
    for (const l of all) {
      const sid = `src-${l.id}`;
      if (m.getLayer(`lyr-${l.id}`)) m.removeLayer(`lyr-${l.id}`);
      if (m.getSource(sid)) m.removeSource(sid);
      m.addSource(sid, { type: "image", url: `${assetBase}/${l.file}`, coordinates: corners(l.bounds) });
      m.addLayer({ id: `lyr-${l.id}`, type: "raster", source: sid, paint: { "raster-opacity": 0, "raster-fade-duration": 250, "raster-resampling": "nearest" } });
    }
    const b = (base[0] ?? overlays[0])?.bounds;
    if (b) m.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 50, duration: 900 });
  }, [ready, result, base, overlays, assetBase]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    base.forEach((l, i) => m.getLayer(`lyr-${l.id}`) && m.setPaintProperty(`lyr-${l.id}`, "raster-opacity", i === period ? 1 : 0));
    overlays.forEach((l) => {
      if (!m.getLayer(`lyr-${l.id}`)) return;
      const visible = l.id === overlay && (l.label === "Change" || l.id.startsWith(periods[period] ?? "") || periods.length < 2);
      m.setPaintProperty(`lyr-${l.id}`, "raster-opacity", visible ? opacity : 0);
    });
  }, [ready, base, overlays, period, overlay, opacity, periods]);

  const n = result?.numbers ?? {};
  const overlayChoices = overlays.filter((o) => o.label === "Change" || o.id.startsWith(periods[period] ?? "") || periods.length < 2);

  return (
    <div className="map-wrap">
      <div ref={el} style={{ position: "absolute", inset: 0 }} />
      {!result && <div className="placeholder" style={{ position: "absolute", inset: 0, zIndex: 4, pointerEvents: "none" }}>Analyze mode outputs appear here as map layers.</div>}
      {result && result.ok && (
        <>
          <div className="map-stats card">
            {result.plan.task === "water_change" ? (
              <>
                <div className="faint" style={{ fontSize: 12 }}>Open water, {periods.join(" → ")}</div>
                <div className="big">
                  {n.water_km2_a?.toFixed(1)} → {n.water_km2_b?.toFixed(1)} <span style={{ fontSize: 15 }} className="muted">km²</span>
                </div>
                <div style={{ color: n.change_km2 >= 0 ? "var(--good)" : "var(--bad)", fontWeight: 650 }}>
                  {n.change_km2 >= 0 ? "+" : ""}
                  {n.change_km2?.toFixed(1)} km² ({n.change_pct >= 0 ? "+" : ""}
                  {n.change_pct?.toFixed(0)} %)
                </div>
              </>
            ) : result.plan.task === "ndvi" ? (
              <>
                <div className="faint" style={{ fontSize: 12 }}>Mean NDVI, {periods[0]}</div>
                <div className="big">{n.mean?.toFixed(2)}</div>
                <div className="muted" style={{ fontSize: 12.5 }}>
                  dense vegetation {(100 * (n.class_fractions?.["dense(>=0.5)"] ?? 0)).toFixed(0)} %
                </div>
              </>
            ) : (
              <>
                <div className="faint" style={{ fontSize: 12 }}>Open water, {periods[0]}</div>
                <div className="big">
                  {n.water_km2?.toFixed(1)} <span style={{ fontSize: 15 }} className="muted">km²</span>
                </div>
              </>
            )}
          </div>
          <div className="map-overlay card">
            {periods.length > 1 && (
              <div className="row">
                <span>Base image</span>
                <div className="seg">
                  {periods.map((p, i) => (
                    <button key={p} className={i === period ? "on" : ""} onClick={() => setPeriod(i)}>
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="row">
              <span>Layer</span>
              <div className="seg">
                {overlayChoices.map((o) => (
                  <button key={o.id} className={o.id === overlay ? "on" : ""} onClick={() => setOverlay(o.id)}>
                    {o.label.replace(/ \d{4}-\d{2}$/, "")}
                  </button>
                ))}
                <button className={overlay === null ? "on" : ""} onClick={() => setOverlay(null)}>
                  None
                </button>
              </div>
              <span style={{ marginLeft: "auto" }}>Opacity</span>
              <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
            </div>
            {overlays.some((o) => o.label === "Change") && overlay?.endsWith("change") && (
              <div className="legend">
                <span><i style={{ background: "#38bdf8" }} />water in both</span>
                <span><i style={{ background: "#22c55e" }} />gained</span>
                <span><i style={{ background: "#f43f5e" }} />lost</span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
