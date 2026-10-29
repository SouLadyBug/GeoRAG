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
    <a href={`#${to}`} className={route === to ? "active" : ""} aria-current={route === to ? "page" : undefined}>
      {label}
    </a>
  );

  return (
    <>
      {/* Hash routing owns the URL fragment, so the skip link moves focus instead of navigating. */}
      <a
        className="skip"
        href="#/"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        Skip to content
      </a>
      <nav className="nav" aria-label="Main">
        <a className="brand" href="#/" aria-label="GeoRAG Copilot, overview">
          <svg className="brand-mark" viewBox="0 0 24 24" fill="none" stroke="#1f5f99" strokeWidth="1.6" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <ellipse cx="12" cy="12" rx="4.5" ry="10" />
            <path d="M2 12h20M4 6.5h16M4 17.5h16" />
          </svg>
          <b>GeoRAG</b>
          <small>Copilot</small>
        </a>
        <div className="nav-links">
          {link("/", "Overview")}
          {link("/copilot", "Copilot")}
          {link("/benchmark", "Benchmark")}
          {link("/sources", "Sources")}
        </div>
        <div className="nav-right">
          <span className="status-pill" title={live ? "Connected to a local GeoRAG server" : "Static site: recorded runs are replayed"}>
            <span className={`dot ${live ? "live" : "demo"}`} />
            {live == null ? "…" : live ? "Live engine" : "Recorded runs"}
          </span>
          <a className="btn small" href="https://github.com/emna-saada/GeoRAG" target="_blank" rel="noreferrer">
            <Github size={15} aria-hidden="true" /> Source code
          </a>
        </div>
      </nav>
      <div id="main" tabIndex={-1} />
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
