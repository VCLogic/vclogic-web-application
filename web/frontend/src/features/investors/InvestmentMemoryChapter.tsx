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

export function InvestmentMemoryChapter({ section }: { section: Chapter }) {
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
      <details aria-label={`Read complete chapter: ${title}`}>
        <summary>Read complete chapter</summary>
        <SafeMarkdown className="memory-body">{section.body}</SafeMarkdown>
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
