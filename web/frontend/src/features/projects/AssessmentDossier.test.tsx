import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { CanonicalAssessment, Investor } from "../../api/types";
import { AssessmentDossier } from "./AssessmentDossier";

const investor:Investor={vc_slug:"yin",display_name:"Elizabeth Yin-like Investor",firm:"Hustle Fund",role:"Partner",disclosure:"Simulation",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]};
const assessment:CanonicalAssessment={assessment_id:"a1",project_id:"p1",version_id:"v1",vc_slug:"yin",pitch_sha256:"a".repeat(64),status:"complete",created_at:"2026-09-01T00:00:00Z",updated_at:"2026-09-01T00:00:00Z",decision:"In",investment_likelihood:.61,decision_confidence:.68,decision_summary:"In at 61% estimated investment likelihood. Strongest signals: Founder Market Fit. Main concerns: Fund Economics Constraint.",decision_justification:"Long original analysis (P-001; W-cafe).",positive_rationales:["founder_market_fit"],negative_rationales:["fund_economics_constraint"],unresolved_rationales:["unit_economics_assessment"],usage:{},rehearsal_session_ids:[],activity:[],citations:[{number:1,reference_id:"P-001",source_type:"pitch",title:"Current pitch",excerpt:"Eight paying agencies.",source_reference:"Immutable pitch version",rationale_labels:["founder_market_fit"]},{number:2,reference_id:"W-cafe",source_type:"investment_memory",title:"Business model economics",excerpt:"Customer acquisition must become repeatable.",source_reference:"persona.md",rationale_labels:["fund_economics_constraint"]}]};

afterEach(cleanup);

it("shows a compact decision dossier and opens traceable evidence", async()=>{
 const user=userEvent.setup();render(<AssessmentDossier assessment={assessment} investor={investor} onRehearse={vi.fn()}/>);
 expect(screen.getByText("Leans In")).toBeVisible();
 expect(screen.getByText("61/100")).toBeVisible();
 expect(screen.getByText("Assessment confidence")).toBeVisible();
 expect(screen.getByText(/not the probability that the real investor will invest/i)).toBeVisible();
 expect(screen.queryByText(/investment likelihood/i)).not.toBeInTheDocument();
 expect(screen.getByText(/strongest signals/i)).toBeVisible();
 expect(screen.queryByText(/long original analysis/i)).not.toBeVisible();
 await user.click(screen.getByRole("button",{name:/evidence 1: current pitch/i}));
 expect(screen.getByText("Eight paying agencies.")).toBeVisible();
 await user.click(screen.getByText("Technical reference"));
 expect(screen.getByText("P-001")).toBeVisible();
 await user.click(screen.getByText(/full model analysis/i));
 expect(screen.getByText(/long original analysis/i)).toBeVisible();
});

it("keeps different evidence sources visible when pitch citations dominate", () => {
 const crowded={...assessment,citations:[
  ...Array.from({length:6},(_,index)=>({...assessment.citations![0],number:index+1,reference_id:`P-00${index+1}`,excerpt:`Pitch fact ${index+1}`})),
  {...assessment.citations![1],number:7,reference_id:"W-cafe"},
 ]};
 render(<AssessmentDossier assessment={crowded} investor={investor} onRehearse={vi.fn()}/>);
 expect(screen.getByRole("button",{name:/evidence 7: business model economics/i})).toBeVisible();
 expect(screen.getAllByRole("button",{name:/evidence \d+:/i})).toHaveLength(5);
});
