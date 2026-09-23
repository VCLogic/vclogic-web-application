import type { InvestorSettingsResponse, CanonicalAssessment, CreateSessionInput, Graph, Investor, InvestorComparison, InvestorMatch, MemorySearchResponse, PitchProject, PitchProjectSummary, PitchVersion, Profile, RehearsalDepth, Session, SessionSummary } from "./types";

export class ApiError extends Error { constructor(public status:number, message:string, public code?:string){ super(message); } }

function fieldName(value: unknown): string {
  return String(value).replace(/_/g, " ").replace(/^./, character => character.toUpperCase());
}

function apiErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const payload = body as Record<string, unknown>;
  const detail = payload.message ?? payload.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => {
      if (!item || typeof item !== "object") return [];
      const issue = item as Record<string, unknown>;
      if (typeof issue.msg !== "string" || !issue.msg.trim()) return [];
      const location = Array.isArray(issue.loc)
        ? issue.loc.filter(part => part !== "body").map(fieldName).join(" → ")
        : "";
      return [`${location ? `${location}: ` : ""}${issue.msg}`];
    });
    if (messages.length) return messages.join(". ");
  }
  if (detail && typeof detail === "object") {
    const nested = detail as Record<string, unknown>;
    if (typeof nested.message === "string" && nested.message.trim()) return nested.message;
  }
  return fallback;
}

async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response=await fetch(path,{...init,headers:{"Content-Type":"application/json",...init?.headers}});
  if(!response.ok){
    const body:unknown=await response.json().catch(()=>({}));
    const code=body && typeof body === "object" && typeof (body as Record<string,unknown>).code === "string" ? (body as Record<string,string>).code : undefined;
    throw new ApiError(response.status,apiErrorMessage(body,response.statusText || "Request failed"),code);
  }
  return response.json() as Promise<T>;
}
export const api={
  investorSettings:()=>request<InvestorSettingsResponse>("/api/settings/investors"),
  refreshInvestors:()=>request<InvestorSettingsResponse>("/api/settings/investors/refresh",{method:"POST"}),
  updateInvestorSettings:(slug:string,body:{enabled:boolean;active_version:string|null})=>request<InvestorSettingsResponse>(`/api/settings/investors/${encodeURIComponent(slug)}`,{method:"PUT",body:JSON.stringify(body)}),
  investors:()=>request<{investors:Investor[]}>("/api/investors"),
  profile:(slug:string)=>request<Profile>(`/api/investors/${slug}`),
  profileGraph:(slug:string)=>request<Graph>(`/api/investors/${slug}/rationale-graph`),
  memory:(slug:string,q:string,page=1,pageSize=5)=>request<MemorySearchResponse>(`/api/investors/${slug}/memory/search?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`),
  sessions:()=>request<{sessions:SessionSummary[]}>("/api/sessions"),
  session:(id:string)=>request<Session>(`/api/sessions/${id}`),
  createSession:(body:CreateSessionInput)=>request<{session_id:string;event_url:string}>("/api/sessions",{method:"POST",body:JSON.stringify(body)}),
  answer:(id:string,text:string)=>request(`/api/sessions/${id}/answers`,{method:"POST",body:JSON.stringify({text})}),
  finish:(id:string)=>request(`/api/sessions/${id}/finish`,{method:"POST"}),
  retry:(id:string)=>request(`/api/sessions/${id}/retry`,{method:"POST"}),
  projects:()=>request<{projects:PitchProjectSummary[]}>("/api/projects"),
  createProject:(body:{display_name:string;company_aliases:string[];pitch_text:string})=>request<PitchProject>("/api/projects",{method:"POST",body:JSON.stringify(body)}),
  project:(id:string)=>request<PitchProject>(`/api/projects/${id}`),
  createVersion:(projectId:string,pitchText:string)=>request<PitchVersion>(`/api/projects/${projectId}/versions`,{method:"POST",body:JSON.stringify({pitch_text:pitchText})}),
  pitchVersion:(projectId:string,versionId:string)=>request<PitchVersion & {pitch_text:string}>(`/api/projects/${projectId}/versions/${versionId}`),
  assessments:(projectId:string,versionId:string)=>request<{assessments:CanonicalAssessment[]}>(`/api/projects/${projectId}/versions/${versionId}/assessments`),
  assessment:(id:string)=>request<CanonicalAssessment>(`/api/assessments/${id}`),
  startAssessment:(projectId:string,versionId:string,vcSlug:string,investorVersionId?:string|null)=>request<{assessment_id:string;status:string;event_url:string}>(`/api/projects/${projectId}/versions/${versionId}/assessments`,{method:"POST",body:JSON.stringify({vc_slug:vcSlug,investor_version_id:investorVersionId,authorize_provider_cost:true})}),
  matches:(projectId:string,versionId:string)=>request<{matches:InvestorMatch[]}>(`/api/projects/${projectId}/versions/${versionId}/matches`),
  match:(id:string)=>request<InvestorMatch>(`/api/matches/${id}`),
  startMatch:(projectId:string,versionId:string,vcSlugs:string[],investorVersions:Record<string,string>={})=>request<{match_id:string;status:string;event_url:string}>(`/api/projects/${projectId}/versions/${versionId}/matches`,{method:"POST",body:JSON.stringify({vc_slugs:vcSlugs,investor_versions:investorVersions,authorize_provider_cost:true})}),
  retryMatch:(id:string,vcSlug:string)=>request<InvestorMatch>(`/api/matches/${id}/retry/${vcSlug}`,{method:"POST"}),
  comparison:(projectId:string,versionId:string)=>request<InvestorComparison>(`/api/projects/${projectId}/versions/${versionId}/comparison`),
  updateComparison:(projectId:string,versionId:string,vcSlugs:string[],authorizeProviderCost:boolean,investorVersions:Record<string,string>={})=>request<InvestorComparison>(`/api/projects/${projectId}/versions/${versionId}/comparison`,{method:"POST",body:JSON.stringify({vc_slugs:vcSlugs,investor_versions:investorVersions,authorize_provider_cost:authorizeProviderCost})}),
  startAssessmentRehearsal:(id:string,depth:RehearsalDepth)=>request<{session_id:string;status:string;event_url:string}>(`/api/assessments/${id}/rehearsals`,{method:"POST",body:JSON.stringify({rehearsal_depth:depth})}),
};
