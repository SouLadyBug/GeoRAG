import { Github } from "lucide-react";
import { useEffect, useState } from "react";
import { detectBackend, loadDemos } from "./api";
import Benchmark from "./pages/Benchmark";
import Copilot from "./pages/Copilot";
import Landing from "./pages/Landing";
import Sources from "./pages/Sources";
import { loadSite, type SiteData } from "./site";
import type { DemoEntry } from "./types";

function useRoute() {
  const get = () => (window.location.hash.replace(/^#/, "").split("?")[0] || "/") as string;
  const [route, setRoute] = useState(get);
  useEffect(() => {
    const on = () => {
      setRoute(get());
      if (!window.location.hash.includes("copilot")) window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export default function App() {
  const route = useRoute();
  const [site, setSite] = useState<SiteData | null>(null);
  const [demos, setDemos] = useState<DemoEntry[]>([]);
  const [live, setLive] = useState<boolean | null>(null);

  useEffect(() => {
    loadSite().then(setSite).catch(() => setSite(null));
    loadDemos().then(setDemos);
    detectBackend().then((h) => setLive(!!h));
  }, []);

  const link = (to: string, label: string) => (
    <a href={`#${to}`} className={route === to ? "active" : ""}>
      {label}
    </a>
  );

  return (
    <>
      <div className="bg-grid" />
      <nav className="nav">
        <a className="brand" href="#/">
          <span className="brand-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#031016" strokeWidth="2.4" strokeLinecap="round">
              <circle cx="12" cy="12" r="8.5" />
              <path d="M3.5 12h17M12 3.5c2.6 2.4 3.8 5.2 3.8 8.5s-1.2 6.1-3.8 8.5c-2.6-2.4-3.8-5.2-3.8-8.5s1.2-6.1 3.8-8.5z" />
            </svg>
          </span>
          GeoRAG <small>Copilot</small>
        </a>
        <div className="nav-links">
          {link("/", "Overview")}
          {link("/copilot", "Copilot")}
          {link("/benchmark", "Benchmark")}
          {link("/sources", "Sources")}
        </div>
        <div className="nav-right">
          <span className="status-pill">
            <span className={`dot ${live ? "live" : "demo"}`} />
            {live == null ? "…" : live ? "Live engine" : "Showcase"}
          </span>
          <a className="btn small" href="https://github.com/emna-saada/GeoRAG" target="_blank" rel="noreferrer">
            <Github size={14} /> GitHub
          </a>
        </div>
      </nav>
      {route === "/copilot" ? (
        <Copilot />
      ) : (
        <>
          {route === "/benchmark" ? <Benchmark site={site} /> : route === "/sources" ? <Sources /> : <Landing site={site} demos={demos} />}
          <footer className="footer">
            <div className="container" style={{ display: "flex", justifyContent: "space-between", gap: 20, flexWrap: "wrap" }}>
              <span>GeoRAG Copilot · code Apache-2.0 · glossary CC BY 4.0 · Sentinel-2 data © Copernicus · {site?.generated ? `results generated ${site.generated}` : ""}</span>
              <span>
                Emna Saada &amp; Souhe Hamdani · <a href="https://github.com/emna-saada/GeoRAG">github.com/emna-saada/GeoRAG</a>
              </span>
            </div>
          </footer>
        </>
      )}
    </>
  );
}
