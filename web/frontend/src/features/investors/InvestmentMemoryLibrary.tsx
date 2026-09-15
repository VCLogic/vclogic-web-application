import { useEffect, useMemo, useState } from "react";
import type { Profile } from "../../api/types";
import { InvestmentMemoryChapter, memoryChapterTitle } from "./InvestmentMemoryChapter";
import { MemorySearch } from "./MemorySearch";

interface InvestmentMemoryLibraryProps {
  vcSlug: string;
  sections: Profile["sections"];
  query: string;
  onQueryChange: (query: string) => void;
}

const CORE_CHAPTERS = new Set(["persona.md", "theses.md", "portfolio_and_constraints.md"]);

function basename(sectionId: string): string {
  return sectionId.split("/").at(-1) ?? sectionId;
}

function defaultSectionId(sections: Profile["sections"]): string {
  return sections.find((section) => basename(section.section_id) === "persona.md")?.section_id
    ?? sections[0]?.section_id
    ?? "";
}

export function InvestmentMemoryLibrary({ vcSlug, sections, query, onQueryChange }: InvestmentMemoryLibraryProps) {
  const fallbackId = defaultSectionId(sections);
  const [selectedId, setSelectedId] = useState(fallbackId);
  useEffect(() => {
    setSelectedId((current) => sections.some((section) => section.section_id === current) ? current : fallbackId);
  }, [fallbackId, sections]);
  const grouped = useMemo(() => ({
    core: sections.filter((section) => CORE_CHAPTERS.has(basename(section.section_id))),
    evidence: sections.filter((section) => !CORE_CHAPTERS.has(basename(section.section_id))),
  }), [sections]);
  const selected = sections.find((section) => section.section_id === selectedId) ?? sections[0];
  const indexGroup = (title: string, items: Profile["sections"]) => items.length > 0 && <div className="memory-index-group">
    <h3>{title}</h3>
    <ol>{items.map((section) => {
      const chapterTitle = memoryChapterTitle(section);
      return <li key={section.section_id}><button type="button" aria-label={`Open ${chapterTitle} chapter`} aria-pressed={selected?.section_id === section.section_id} onClick={() => setSelectedId(section.section_id)}><span>{chapterTitle}</span><small>{(section.character_count ?? section.body.length).toLocaleString()} chars</small></button></li>;
    })}</ol>
  </div>;

  return <section className="investment-memory-library" aria-labelledby="investment-memory-title">
    <header className="memory-library-heading"><span className="section-index">03 / Source library</span><h2 id="investment-memory-title">Investment Memory</h2><p>Search the supporting record or inspect one indexed chapter at a time.</p></header>
    <MemorySearch key={vcSlug} vcSlug={vcSlug} query={query} onQueryChange={onQueryChange} />
    {sections.length ? <div className="memory-library-layout">
      <nav className="memory-chapter-index" aria-label="Investment Memory chapters">
        <label htmlFor="memory-chapter-select">Browse chapters</label>
        <select id="memory-chapter-select" aria-label="Choose Investment Memory chapter" value={selected?.section_id} onChange={(event) => setSelectedId(event.target.value)}>{sections.map((section) => <option key={section.section_id} value={section.section_id}>{memoryChapterTitle(section)}</option>)}</select>
        <div className="memory-index-desktop">{indexGroup("Core profile", grouped.core)}{indexGroup("Evidence library", grouped.evidence)}</div>
      </nav>
      {selected && <InvestmentMemoryChapter key={selected.section_id} section={selected} />}
    </div> : <p className="memory-library-empty">No Investment Memory chapters are available for this profile.</p>}
  </section>;
}
