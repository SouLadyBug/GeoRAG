import { useEffect, useMemo, useState } from "react";
import { getJSON } from "../api";

interface Row {
  doc_id: string;
  source: string;
  domain: string;
  title: string;
  authors: string;
  year: number | null;
  url: string | null;
  licence: string | null;
}

const DOMAINS: Record<string, string> = {
  gis: "GIS",
  remote_sensing: "Remote sensing",
  lidar: "LiDAR",
  digital_twin: "Digital twins",
  geo_cv: "Geo CV",
  docs: "Documentation",
  catalogue: "Datasets",
  glossary: "Glossary",
};

function licenceLabel(l: string | null) {
  if (!l) return "—";
  if (l.includes("arxiv.org/licenses/nonexclusive")) return "arXiv non-exclusive";
  const m = l.match(/creativecommons\.org\/licenses\/([a-z-]+)\/([\d.]+)/);
  if (m) return `CC ${m[1].toUpperCase()} ${m[2]}`;
  if (l.includes("publicdomain/zero")) return "CC0 1.0";
  return l.length > 40 ? `${l.slice(0, 40)}…` : l;
}

export default function Sources() {
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState<string>("");
  const [limit, setLimit] = useState(150);

  useEffect(() => {
    getJSON<Row[]>("data/sources.json").then(setRows).catch(() => setRows([]));
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => (!domain || r.domain === domain) && (!needle || r.title.toLowerCase().includes(needle) || r.authors.toLowerCase().includes(needle)));
  }, [rows, q, domain]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    rows.forEach((r) => (c[r.domain] = (c[r.domain] ?? 0) + 1));
    return c;
  }, [rows]);

  return (
    <div className="page">
      <section className="section" style={{ paddingBottom: 30 }}>
        <div className="container">
          <div className="eyebrow">Licence register</div>
          <h2 className="title">Sources</h2>
          <p className="lead">
            Every document in the index, generated from <code>corpus/manifest.parquet</code>. Paper metadata and abstracts come from the arXiv snapshot, released under CC0; the licence column shows the licence of each paper itself. Documentation keeps its project licence.
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "24px 0 16px" }}>
            <button className={`btn small${domain === "" ? " primary" : ""}`} onClick={() => setDomain("")}>
              All {rows.length.toLocaleString()}
            </button>
            {Object.entries(DOMAINS)
              .filter(([k]) => counts[k])
              .map(([k, v]) => (
                <button key={k} className={`btn small${domain === k ? " primary" : ""}`} onClick={() => setDomain(k)}>
                  {v} {counts[k]}
                </button>
              ))}
          </div>
          <input className="search" placeholder="Filter by title or author…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="card" style={{ marginTop: 16, overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Domain</th>
                  <th className="num">Year</th>
                  <th>Licence</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, limit).map((r) => (
                  <tr key={r.doc_id}>
                    <td>
                      {r.url ? (
                        <a href={r.url} target="_blank" rel="noreferrer">
                          {r.title}
                        </a>
                      ) : (
                        r.title
                      )}
                      <div className="faint" style={{ fontSize: 12 }}>
                        {r.authors.split("; ").slice(0, 4).join(", ")}
                        {r.authors.split("; ").length > 4 ? " et al." : ""}
                      </div>
                    </td>
                    <td className="muted" style={{ whiteSpace: "nowrap" }}>{DOMAINS[r.domain] ?? r.domain}</td>
                    <td className="num">{r.year ?? ""}</td>
                    <td className="muted" style={{ fontSize: 12.5, whiteSpace: "nowrap" }}>{licenceLabel(r.licence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length > limit && (
            <div style={{ textAlign: "center", marginTop: 16 }}>
              <button className="btn" onClick={() => setLimit((l) => l + 300)}>
                Show more ({(filtered.length - limit).toLocaleString()} left)
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
