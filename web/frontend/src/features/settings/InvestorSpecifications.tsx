import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type { InvestorSpecifications as Specifications } from "../../api/types";
import "./settings.css";

function FieldValue({ value }: { value: Specifications["sections"][number]["fields"][number]["value"] }) {
  if (value === null || value === "") return <>Not specified</>;
  if (typeof value === "boolean") return <>{value ? "Yes" : "No"}</>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}>{item}</li>)}</ul> : <>None</>;
  return <>{value}</>;
}

export function InvestorSpecifications() {
  const { vcSlug = "" } = useParams();
  const [params] = useSearchParams();
  const version = params.get("version") || undefined;
  const query = useQuery({
    queryKey: ["investor-specifications", vcSlug, version],
    queryFn: () => api.investorSpecifications(vcSlug, version),
  });
  const specifications = query.data;
  return <section className="investor-settings investor-specifications">
    <Link to="/settings/investors">Back to investor settings</Link>
    <header className="settings-header"><div><h1>Investor specifications</h1><p>Prepared configuration: read-only defaults for this investor version, rather than a snapshot of an assessment run. Viewing specifications does not run an assessment or change the active version.</p></div></header>
    {query.isPending && <p role="status">Loading investor specifications…</p>}
    {query.error && <div role="alert" className="error"><p>{query.error.message}</p><button type="button" onClick={() => query.refetch()}>Try again</button></div>}
    {specifications && <>
      <section className="specification-identity" aria-label="Investor version">
        <h2>{specifications.display_name}</h2>
        <p>{specifications.version_label}</p>
        <dl className="specification-fields">
          <div><dt>Version fingerprint</dt><dd><code>{specifications.investor_version_id}</code></dd></div>
          <div><dt>Selection</dt><dd>{specifications.active ? "Active version" : "Alternative version"}</dd></div>
          <div><dt>Investor availability</dt><dd>{specifications.enabled ? "Enabled for new assessments" : "Disabled for new assessments"}</dd></div>
          <div><dt>Version readiness</dt><dd>{specifications.ready ? "Ready" : "Not ready"}</dd></div>
        </dl>
        {specifications.error && <p className="setting-problem">{specifications.error}</p>}
      </section>
      {specifications.notes.length > 0 && <aside className="specification-notes" aria-label="Configuration notes"><ul>{specifications.notes.map((note, index) => <li key={index}>{note}</li>)}</ul></aside>}
      {specifications.sections.map(section => <section className="specification-section" key={section.id} aria-labelledby={`specification-${section.id}`}>
        <h2 id={`specification-${section.id}`}>{section.title}</h2>
        <dl className="specification-fields">{section.fields.map((field, index) => <div key={index}><dt>{field.label}</dt><dd><FieldValue value={field.value}/></dd></div>)}</dl>
      </section>)}
      <details className="specification-taxonomy"><summary>Decision taxonomy ({specifications.taxonomy.length} rationales)</summary>
        {specifications.taxonomy.length ? <dl className="specification-fields">{specifications.taxonomy.map(row => <div key={row.label}><dt>{row.label}</dt><dd><p>{row.definition || "Definition not specified."}</p>{row.coarse_parent && <small>Theme: {row.coarse_parent}</small>}</dd></div>)}</dl> : <p>No taxonomy is available for this version.</p>}
      </details>
    </>}
  </section>;
}
