import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "../../api/client";
import type { MemorySearchResponse } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";

interface MemorySearchProps {
  vcSlug: string;
  query: string;
  onQueryChange: (query: string) => void;
}

const PAGE_SIZE = 5;

function humanize(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
}

function humanizeSourcePath(path: string): string {
  const filename = path.split("/").at(-1)?.replace(/\.[^.]+$/, "") || "Investment memory source";
  return humanize(filename).replace(/\b\w/g, (character) => character.toUpperCase());
}

export function MemorySearch({ vcSlug, query, onQueryChange }: MemorySearchProps) {
  const [input, setInput] = useState(query);
  const normalizedQuery = query.trim();
  const [pagination, setPagination] = useState({ query: normalizedQuery, page: 1 });
  const [lastSuccessful, setLastSuccessful] = useState<{
    query: string;
    data: MemorySearchResponse;
  } | null>(null);
  const page = pagination.query === normalizedQuery ? pagination.page : 1;

  useEffect(() => setInput(query), [query]);

  const { data, error, isError, isFetching, refetch } = useQuery({
    queryKey: ["memory", vcSlug, normalizedQuery, page],
    queryFn: () => api.memory(vcSlug, normalizedQuery, page, PAGE_SIZE),
    enabled: normalizedQuery.length >= 2,
    placeholderData: (previous, previousQuery) => (
      previousQuery?.queryKey[2] === normalizedQuery ? previous : undefined
    ),
  });

  useEffect(() => {
    if (data) setLastSuccessful({ query: normalizedQuery, data });
  }, [data, normalizedQuery]);

  const displayedData = data ?? (
    lastSuccessful?.query === normalizedQuery ? lastSuccessful.data : undefined
  );
  const resultPage = displayedData?.page ?? 1;
  const totalResults = displayedData?.total_results ?? displayedData?.results.length ?? 0;
  const totalPages = displayedData?.total_pages ?? (totalResults > 0 ? 1 : 0);
  const firstResult = totalResults === 0 ? 0 : (resultPage - 1) * PAGE_SIZE + 1;
  const lastResult = Math.min(resultPage * PAGE_SIZE, totalResults);

  function submitSearch(): void {
    const submittedQuery = input.trim();
    setPagination({ query: submittedQuery, page: 1 });
    if (submittedQuery === normalizedQuery) {
      if (page === 1) void refetch();
      return;
    }
    onQueryChange(submittedQuery);
  }

  return <section className="memory-search card" aria-labelledby="memory-search-title">
    <h2 id="memory-search-title">Search the Investment Memory</h2>
    <p>Inspect the source-linked public evidence behind the profile.</p>
    <form onSubmit={(event) => { event.preventDefault(); submitSearch(); }}>
      <input aria-label="Search investment memory" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Try ‘founder conviction’ or ‘portfolio conflict’" />
      <button className="button"><Search size={16} /> Search</button>
    </form>
    {isFetching && <p role="status">Searching sources…</p>}
    {isError && <div className="memory-search-error" role="alert">
      <p>Unable to search the Investment Memory{error instanceof Error && error.message ? `: ${error.message}` : "."}</p>
      <button type="button" onClick={() => refetch()}>Retry memory search</button>
    </div>}
    <div className="memory-results" aria-live="polite">
      {displayedData?.results.map((result, index) => {
        const sourceTitle = result.source_title ?? humanizeSourcePath(result.source_path);
        const resultNumber = firstResult + index;
        return <article
          className="memory-result"
          aria-label={`Evidence ${resultNumber} of ${totalResults} from ${sourceTitle}`}
          key={`${result.source_path}:${result.evidence_id}`}
        >
          <header>
            <strong>{sourceTitle}</strong>
            <span className="memory-result-tags">
              {result.rationale_label && <span className="pill">{humanize(result.rationale_label)}</span>}
              {result.direction && <span className={`pill direction-${result.direction}`}>{result.direction}</span>}
            </span>
          </header>
          <SafeMarkdown className="memory-result-excerpt">{result.excerpt}</SafeMarkdown>
          <details aria-label={`Source details: ${sourceTitle}`}>
            <summary>Source details</summary>
            {result.source_reference && <p><strong>Public source:</strong> {result.source_reference}</p>}
            <p><strong>Evidence ID:</strong> {result.evidence_id}</p>
            <p><strong>Source type:</strong> {result.source_kind}</p>
            <code>{result.source_path}</code>
          </details>
        </article>;
      })}
      {displayedData && displayedData.results.length === 0 && <p className="memory-no-results">No supporting evidence found.</p>}
    </div>
    {displayedData && totalResults > 0 && <footer className="memory-pagination">
      <p role="status">Showing {firstResult}–{lastResult} of {totalResults}</p>
      {totalPages > 1 && <>
        <p>Page {resultPage} of {totalPages}</p>
        <div>
          <button
            type="button"
            aria-label="Previous evidence page"
            disabled={resultPage <= 1}
            onClick={() => setPagination({ query: normalizedQuery, page: resultPage - 1 })}
          >Previous</button>
          <button
            type="button"
            aria-label="Next evidence page"
            disabled={resultPage >= totalPages}
            onClick={() => setPagination({ query: normalizedQuery, page: resultPage + 1 })}
          >Next</button>
        </div>
      </>}
    </footer>}
  </section>;
}
