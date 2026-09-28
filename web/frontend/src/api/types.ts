export type Direction = "positive" | "negative" | "neutral" | "mixed" | "unresolved";
export type RehearsalDepth = "quick" | "standard" | "deep";
export type EvidenceEffect = "new_positive" | "new_negative" | "clarification" | "unresolved" | "contradiction";
export interface CreateSessionInput { investor_version_id?:string|null; vc_slug:string; company_aliases:string[]; pitch_text:string; authorize_provider_cost:true; rehearsal_depth:RehearsalDepth }
export interface Investor { investor_version_id?:string|null; vc_slug:string; display_name:string; firm:string; role:string; disclosure:string; start_available:boolean; summary?:string; evidence_coverage?:number; portrait_path?:string; portrait_alt?:string; source_profile_url?:string; photo_attribution?:string; recurring_positive_rationales:string[]; recurring_negative_rationales:string[]; recurring_unresolved_rationales?:string[]; recurring_positive_counts?:Record<string,number>|null; recurring_negative_counts?:Record<string,number>|null; recurring_unresolved_counts?:Record<string,number>|null }
export interface Evidence { evidence_id:string; source_kind:string; source_path:string; excerpt:string; confidence?:number; source_title?:string|null; rationale_label?:string|null; direction?:Direction|null; source_reference?:string|null }
export interface MemorySearchResponse { results:Evidence[]; page?:number; page_size?:number; total_results?:number; total_pages?:number }
export interface RationaleNode { node_id:string; taxonomy_label:string; title:string; direction:Direction; salience:string; confidence:number; evidence_ids:string[]; initial_direction?:string|null; initial_confidence?:number|null; definition?:string|null; coarse_parent?:string|null; occurrence_count?:number|null; investigation_count?:number|null; direction_counts?:Record<string,number>|null; weighted_degree?:number|null }
export interface Graph { evidence_status?:"available"|"not_prepared"|"invalid"; evidence_note?:string|null; nodes:RationaleNode[]; edges:{edge_id:string;source:string;target:string;relationship:string;inference_status:string;evidence_ids:string[];occurrence_count?:number|null}[] }
export interface Assessment { decision:"In"|"Out"; investment_likelihood:number; decision_confidence:number; review_priority_score?:number; rationale_counts:Record<string,number>; decision_justification?:string; score_reconciliation?:string|null }
export interface AgentActivity { activity_id:string; phase:"phase1"|"phase2"; iteration:number; kind:"plan"|"investigation"|"decision"; status:"complete"|"failed"; title:string; text:string; details:string[]; elapsed_seconds?:number|null }
export interface ConversationTurn { question_id:string; question:string; response_comment?:string|null; rationale_labels:string[]; founder_answer?:string|null; answer_sha256?:string|null; evidence_effect?:EvidenceEffect|null; investment_likelihood_before?:number|null; investment_likelihood_after?:number|null; likelihood_delta?:number|null }
export interface LikelihoodTimeline { turn:number; label:string; evidence_effect:"baseline"|"synthesis"|EvidenceEffect; before:number; after:number; delta:number; answer_excerpt?:string|null }
export interface DecisionPath { path_id:string; evidence_id:string; evidence_origin:"pitch"|"founder_answer"; evidence_excerpt:string; rationale_id:string; rationale_label:string; direction:"positive"|"negative"|"unresolved"; contribution:string; baseline_or_rehearsal:"baseline"|"rehearsal"; supporting_evidence_ids:string[] }
export interface Session { investor_version_id?:string|null; session_id:string; vc_slug:string; investor_display_name:string; disclosure:string; status:string; operation_active?:boolean; rehearsal_depth?:RehearsalDepth; pitch_text:string; pitch_sha256:string; initial_assessment?:Assessment; current_assessment?:Assessment; active_question?:{question_id:string;text:string;rationale_labels:string[];decision_relevance?:string|null;response_comment?:string|null}; conversation?:ConversationTurn[]; likelihood_timeline?:LikelihoodTimeline[]; decision_path?:DecisionPath[]; max_questions?:number; closing_message?:string|null; agent_activity?:AgentActivity[]; turns:Record<string,unknown>[]; annotations:{annotation_id:string;start:number;end:number;text:string;direction:Direction;rationale_ids:string[];evidence_ids:string[]}[]; rationale_graph?:Graph; evidence:Evidence[]; usage:Record<string,number>; findings:string[] }
export interface SessionSummary { session_id:string; vc_slug:string; investor_display_name:string; company_aliases:string[]; status:string; created_at:string; initial_decision?:string; initial_likelihood?:number; current_decision?:string; current_likelihood?:number; cost_usd?:number; verification_status:string }
export interface Profile { investor:Investor; sections:{section_id:string;title:string;body:string;source_paths:string[];preview?:string|null;character_count?:number|null}[] }
export interface PitchVersion { version_id:string; project_id:string; created_at:string; pitch_sha256:string; character_count:number; pitch_text?:string }
export interface PitchProjectSummary { project_id:string; display_name:string; company_aliases:string[]; created_at:string; updated_at:string; current_version_id:string; version_count:number; assessment_count:number; rehearsal_count:number }
export interface PitchProject extends PitchProjectSummary { versions:PitchVersion[] }
export type AssessmentStatus="queued"|"running"|"complete"|"failed";
export interface AssessmentActivity { stage:string; title:string; detail:string; status:"pending"|"active"|"complete"|"failed"; timestamp?:string|null }
export interface AssessmentCitation { number:number; reference_id:string; source_type:"pitch"|"investment_memory"|"precedent"|"rationale"|"unavailable"; title:string; excerpt?:string|null; source_reference?:string|null; episode_slug?:string|null; decision_status?:string|null; rationale_labels:string[] }
export interface CanonicalAssessment { investor_version_id?:string|null; assessment_id:string; project_id:string; version_id:string; vc_slug:string; pitch_sha256:string; status:AssessmentStatus; created_at:string; updated_at:string; canonical_run_path?:string|null; contract_version?:string|null; phase1_status?:string|null; phase2_status?:string|null; decision?:"In"|"Out"|null; investment_likelihood?:number|null; decision_confidence?:number|null; review_priority_score?:number|null; decision_justification?:string|null; decision_summary?:string|null; citations?:AssessmentCitation[]; activity?:AssessmentActivity[]; positive_rationales:string[]; negative_rationales:string[]; unresolved_rationales:string[]; usage:Record<string,number>; public_error?:string|null; rehearsal_session_ids:string[] }
export interface RelativeFit { percentile?:number|null; reference_count:number }
export interface MatchAssessment { investor_version_id?:string|null; assessment_id:string; vc_slug:string; status:AssessmentStatus; decision?:"In"|"Out"|null; investment_likelihood?:number|null; decision_confidence?:number|null; positive_rationales:string[]; negative_rationales:string[]; unresolved_rationales:string[]; relative_fit:RelativeFit; highest_estimated_fit:boolean; leading_group:boolean; public_error?:string|null; reused?:boolean }
export interface InvestorMatch { match_id:string; project_id:string; version_id:string; selected_vc_slugs:string[]; status:"queued"|"running"|"complete"|"partial"|"failed"; created_at:string; updated_at:string; assessments:MatchAssessment[] }
export interface InvestorComparison { comparison_id:string; project_id:string; version_id:string; selected_vc_slugs:string[]; status:"queued"|"running"|"complete"|"partial"|"failed"; created_at:string; updated_at:string; missing_vc_slugs:string[]; assessments:MatchAssessment[] }

export interface InvestorVersion {
  version_id: string;
  label: string;
  ready: boolean;
  error?: string | null;
  created_at?: string | null;
  capabilities: Record<string, boolean>;
}
export interface InvestorSetting {
  vc_slug: string;
  display_name: string;
  enabled: boolean;
  available: boolean;
  active_version: string | null;
  versions: InvestorVersion[];
}
export interface InvestorSettingsResponse {
  investors: InvestorSetting[];
  discovery_errors: string[];
}
