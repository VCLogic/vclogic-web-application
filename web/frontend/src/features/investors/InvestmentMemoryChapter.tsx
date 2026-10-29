import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useState } from "react";
import type { Profile } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";

type Chapter = Profile["sections"][number];

export function memoryChapterTitle(section: Chapter): string {
  const title = section.title.trim();
  if (!title) return "Untitled chapter";
  if (/\s/.test(title)) return title;
  const humanized = title.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  return humanized.charAt(0).toUpperCase() + humanized.slice(1);
}

function previewFor(section: Chapter): string {
  const supplied = section.preview?.trim();
  if (supplied) return supplied;
  const body = section.body.trim();
  if (!body) return "No chapter preview is available.";
  return body.length > 360 ? `${body.slice(0, 357).trimEnd()}…` : body;
}

export function InvestmentMemoryChapter({ section, onFindEvidence, vcSlug }: { section: Chapter; vcSlug?:string; onFindEvidence?: (query: string) => void }) {
  const [open, setOpen] = useState(false);
  const loaded = useQuery({
    queryKey:["wiki-chapter", vcSlug, section.memory_version, section.section_id],
    queryFn:()=>api.chapter(vcSlug!, section.section_id, section.memory_version),
    enabled:open && section.body_loaded === false && !!vcSlug,
    staleTime:Infinity,
  });
  const body = section.body_loaded === false ? loaded.data?.body ?? "" : section.body;
  const title = memoryChapterTitle(section);
  const headingId = `memory-reader-${section.section_id.replace(/[^a-z0-9]+/gi, "-")}`;
  const characterCount = typeof section.character_count === "number" && Number.isFinite(section.character_count)
    ? Math.max(0, section.character_count)
    : section.body.length;
  const sourceCount = section.source_paths.length;

  return <article className="memory-reader" aria-label={`Investment Memory chapter: ${title}`}>
    <header><span className="memory-reader-label">Selected chapter</span><h3 id={headingId}>{title}</h3><p>{characterCount.toLocaleString()} {characterCount === 1 ? "character" : "characters"} · {sourceCount} {sourceCount === 1 ? "source" : "sources"}</p></header>
    <p className="memory-reader-preview">{previewFor(section)}</p>
    <div className="memory-reader-actions">
      <details aria-label={`Read complete chapter: ${title}`} onToggle={event => setOpen(event.currentTarget.open)}>
        <summary>Read complete chapter</summary>
        {open && section.body_loaded === false && loaded.isPending && <p role="status">Loading complete chapter…</p>}
        {open && loaded.error && <p role="alert">{loaded.error.message} <button onClick={() => loaded.refetch()}>Retry chapter</button></p>}
        {open && body && <SafeMarkdown className="memory-body" components={onFindEvidence ? {a: ({href, children}) => href?.startsWith("#wiki-evidence-")
          ? <button className="text-link" type="button" onClick={() => { onFindEvidence(href.slice("#wiki-evidence-".length)); document.getElementById("memory-search-title")?.scrollIntoView?.({block:"start"}); }}>{children}</button>
          : <a href={href} target={/^https?:/.test(href || "") ? "_blank" : undefined} rel="noreferrer noopener">{children}</a>} : undefined}>
          {onFindEvidence ? body.replace(/\[(ev|ctx):([a-zA-Z0-9_-]+)\]/g, "[$1 evidence](#wiki-evidence-$1:$2)") : body}
        </SafeMarkdown>}
      </details>
      <details aria-label={`Inspect sources: ${title}`}>
        <summary>Inspect sources ({sourceCount})</summary>
        <div className="chapter-sources">
          {sourceCount > 0 ? section.source_paths.map((path) => <code key={path}>{path}</code>) : <p>No source files listed.</p>}
        </div>
      </details>
    </div>
  </article>;
}
