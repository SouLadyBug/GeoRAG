import { marked } from "marked";
import { Fragment, useMemo } from "react";
import type { Sentence } from "../types";

interface CiteProps {
  n: number;
  active?: boolean;
  onPick?: (n: number) => void;
}

export function Cite({ n, active, onPick }: CiteProps) {
  return (
    <span className={`cite${active ? " active" : ""}`} onClick={() => onPick?.(n)} title={`Source ${n}`}>
      {n}
    </span>
  );
}

/** Render Ask-mode sentences with citation chips; unsupported sentences get a wavy underline. */
export function CitedSentences({ sentences, active, onPick }: { sentences: Sentence[]; active?: number | null; onPick: (n: number) => void }) {
  return (
    <p>
      {sentences.map((s, i) => (
        <Fragment key={i}>
          <span
            className={s.supported ? undefined : "unsupported"}
            title={s.supported ? (s.support != null ? `support ${s.support.toFixed(2)}` : undefined) : "No cited passage supports this sentence"}
          >
            {s.text.replace(/[.?!]$/, "")}
          </span>
          {s.citations.map((n) => (
            <Cite key={n} n={n} active={active === n} onPick={onPick} />
          ))}
          {/[?!]$/.test(s.text) ? s.text.slice(-1) : "."}{" "}
        </Fragment>
      ))}
    </p>
  );
}

/** Markdown with `[n]` citation markers turned into clickable chips and ⚠ flags into warnings. */
export function CitedMarkdown({ markdown, onPick }: { markdown: string; onPick: (n: number) => void }) {
  const html = useMemo(() => {
    const raw = marked.parse(markdown, { async: false }) as string;
    return raw
      .replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_m, g: string) =>
        g
          .split(/\s*,\s*/)
          .map((n) => `<span class="cite" data-n="${n}">${n}</span>`)
          .join(""),
      )
      .replace(/ ⚠/g, ' <span class="chip warn" title="No cited passage supports this statement" style="padding:0 6px;font-size:12px">not in sources</span>');
  }, [markdown]);
  return (
    <div
      className="md"
      dangerouslySetInnerHTML={{ __html: html }}
      onClick={(e) => {
        const t = e.target as HTMLElement;
        if (t.classList.contains("cite")) onPick(Number(t.dataset.n));
      }}
    />
  );
}
