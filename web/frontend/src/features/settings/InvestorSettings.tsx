import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../../api/client";
import type { InvestorSetting, InvestorSettingsResponse } from "../../api/types";
import "./settings.css";

const capabilities: Record<string, string> = {
  wiki: "Investment memory", precedents: "Past pitch decisions",
  portfolio_memory: "Portfolio evidence", classifier: "Trained classifier",
};

function InvestorRow({ investor, onSaved }: { investor: InvestorSetting; onSaved: (data: InvestorSettingsResponse) => void }) {
  const [enabled, setEnabled] = useState(investor.enabled);
  const [version, setVersion] = useState(investor.active_version ?? "");
  const [saved, setSaved] = useState(false);
  const dirty = enabled !== investor.enabled || version !== (investor.active_version ?? "");
  const previous = useRef({enabled: investor.enabled, version: investor.active_version ?? ""});
  useEffect(() => {
    // Accept external updates only when the user has not edited the previous values.
    if (enabled === previous.current.enabled && version === previous.current.version) {
      setEnabled(investor.enabled); setVersion(investor.active_version ?? "");
    }
    previous.current = {enabled: investor.enabled, version: investor.active_version ?? ""};
  }, [investor.enabled, investor.active_version, enabled, version]);
  const selected = investor.versions.find(row => row.version_id === version);
  const save = useMutation({
    mutationFn: () => api.updateInvestorSettings(investor.vc_slug, { enabled, active_version: version || null }),
    onSuccess: data => { onSaved(data); setSaved(true); },
  });
  const change = () => { setSaved(false); save.reset(); };
  const status = investor.enabled ? (investor.available ? "Enabled" : "Needs attention") : "Disabled";
  return <form className="investor-setting" aria-label={investor.display_name} onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <div className="setting-identity">
      <h2>{investor.display_name}<span className="setting-simulation">Investor-like simulation</span></h2>
      <p className={`setting-state ${investor.enabled && investor.available ? "is-enabled" : ""}`}>{status}</p>
      <p>{investor.versions.length} {investor.versions.length === 1 ? "version" : "versions"} discovered</p>
    </div>
    <div className="setting-controls">
      <label className="setting-toggle"><input type="checkbox" checked={enabled}
        disabled={save.isPending || (!selected?.ready && !enabled)}
        onChange={event => { change(); setEnabled(event.target.checked); }} />Enabled for new assessments</label>
      <label className="setting-version">Active version
        <select value={version} disabled={save.isPending} onChange={event => { change(); setVersion(event.target.value); }}>
          <option value="" disabled>Choose a ready version</option>
          {version && !selected && <option value={version} disabled>Selected version is unavailable</option>}
          {investor.versions.map(row => <option key={row.version_id} value={row.version_id} disabled={!row.ready}>
            {row.label} · {row.version_id.slice(0, 8)}{row.ready ? "" : " · Not ready"}
          </option>)}
        </select>
      </label>
      {selected && <p><Link to={`/settings/investors/${encodeURIComponent(investor.vc_slug)}/specifications?version=${encodeURIComponent(selected.version_id)}`}>View selected version specifications</Link></p>}
      {selected && <p className="setting-capabilities">{Object.entries(selected.capabilities).filter(([, available]) => available).map(([key]) => capabilities[key] || key).join(" · ") || "No assessment capabilities available"}</p>}
      {selected?.created_at && <p className="setting-date">Prepared {new Date(selected.created_at).toLocaleString()}</p>}
      {!selected && version && <p className="setting-problem">The selected version is missing. Restore it or select another ready version.</p>}
      {investor.versions.filter(row => !row.ready).map(row => <p className="setting-problem" key={row.version_id}><strong>{row.label}: </strong>{row.error || "Finish onboarding before using this version."} <Link to={`/settings/investors/${encodeURIComponent(investor.vc_slug)}/specifications?version=${encodeURIComponent(row.version_id)}`}>Inspect {row.label} specifications</Link></p>)}
      <div className="setting-save">
        <button className="button" type="submit" disabled={!dirty || save.isPending || (enabled && !selected?.ready)}>{save.isPending ? "Saving…" : "Save changes"}</button>
        {saved && <span role="status">Settings saved.</span>}
      </div>
      {save.error && <p role="alert" className="error">{save.error.message}</p>}
    </div>
  </form>;
}

export function InvestorSettings() {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: ["investor-settings"], queryFn: api.investorSettings, refetchInterval: 30_000 });
  const onSaved = (data: InvestorSettingsResponse) => {
    client.setQueryData(["investor-settings"], data);
    for (const key of ["investors", "profile", "profile-graph", "investor-specifications"]) client.invalidateQueries({ queryKey: [key] });
  };
  const refresh = useMutation({ mutationFn: api.refreshInvestors, onSuccess: onSaved });
  return <section className="investor-settings">
    <header className="settings-header"><div><h1>Investor settings</h1><p>Choose which investor simulations are available and the version used for new assessments.</p></div>
      <button className="button secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}><RefreshCw size={16} aria-hidden="true"/>{refresh.isPending ? "Discovering…" : "Refresh investors"}</button>
    </header>
    <p className="settings-context">Onboarded investors appear automatically. Each investor has one active version. Switching versions or disabling an investor keeps saved assessments and existing rehearsals intact.</p>
    {settings.isPending && <p role="status">Discovering investor versions…</p>}
    {settings.error && <div role="alert"><p>{settings.error.message}</p><button onClick={() => settings.refetch()}>Try again</button></div>}
    {refresh.error && <p role="alert" className="error">{refresh.error.message}</p>}
    {refresh.isSuccess && <p role="status">Investor discovery is up to date.</p>}
    {settings.data?.discovery_errors.map((error, index) => <p className="setting-problem" key={index}>{error}</p>)}
    {settings.data?.investors.length === 0 && <div className="settings-empty"><h2>No investors discovered</h2><p>Prepare an investor bundle through onboarding or install it into the assessment workspace, then refresh this list.</p></div>}
    <div className="settings-register">{settings.data?.investors.map(investor => <InvestorRow key={investor.vc_slug} investor={investor} onSaved={onSaved}/>)}</div>
  </section>;
}
