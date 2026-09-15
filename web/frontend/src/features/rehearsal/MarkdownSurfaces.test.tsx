import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../../api/types";
import { AssessmentPanel } from "./AssessmentPanel";
import { ConversationPanel } from "./ConversationPanel";
import { DecisionPath } from "./DecisionPath";
import { EvidenceDrawer } from "./EvidenceDrawer";

afterEach(cleanup);

describe("rehearsal Markdown surfaces", () => {
  it("renders decision justification and path prose semantically", () => {
    render(<>
      <AssessmentPanel initial={{decision:"In",investment_likelihood:.6,decision_confidence:.7,rationale_counts:{},decision_justification:"**Paid adoption** supports conviction."}} onEvidence={vi.fn()} />
      <DecisionPath finalDecision="In" onEvidence={vi.fn()} rows={[{path_id:"p1",evidence_id:"e1",evidence_origin:"pitch",evidence_excerpt:"- **Eight customers**\n- $18k MRR",rationale_id:"r1",rationale_label:"product_adoption",direction:"positive",contribution:"The company shows **real usage**.",baseline_or_rehearsal:"baseline",supporting_evidence_ids:[]}]} />
    </>);
    expect(screen.getByText("Paid adoption").tagName).toBe("STRONG");
    expect(screen.getByText("real usage").tagName).toBe("STRONG");
    expect(document.querySelectorAll(".path-evidence-excerpt li")).toHaveLength(2);
  });

  it("turns internal assessment references into linked, readable footnotes", async () => {
    const user = userEvent.setup();
    const onEvidence = vi.fn();
    render(<AssessmentPanel
      initial={{decision:"In",investment_likelihood:.64,decision_confidence:.66,rationale_counts:{},decision_justification:"Paid demand is visible (P-020; W-cafe), while repeatability remains unresolved (R7). P-020 is the strongest signal."}}
      graph={{nodes:[{node_id:"R7",taxonomy_label:"traction_repeatability_concern",title:"Traction Repeatability Concern",direction:"negative",salience:"primary",confidence:.8,evidence_ids:["W-cafe"]}],edges:[]}}
      evidence={[
        {evidence_id:"P-020",source_kind:"pitch",source_path:"pitch.md",excerpt:"Eight paying agencies."},
        {evidence_id:"W-cafe",source_kind:"wiki",source_path:"traction.md",excerpt:"Repeatable acquisition matters."},
      ]}
      onEvidence={onEvidence}
    />);

    expect(screen.queryByText(/P-020|W-cafe|R7/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button",{name:/source 1.*current pitch/i})).toHaveLength(3);
    expect(screen.getByText("3 sources cited")).toBeVisible();
    await user.click(screen.getAllByRole("button",{name:/source 2.*investment memory/i})[0]);
    expect(onEvidence).toHaveBeenCalledWith(["W-cafe"]);
    await user.click(screen.getAllByRole("button",{name:/source 3.*traction repeatability concern/i})[0]);
    expect(onEvidence).toHaveBeenCalledWith(["W-cafe"]);
  });

  it("renders conversation and evidence excerpts without exposing Markdown syntax", () => {
    const session = {session_id:"s",vc_slug:"yin",investor_display_name:"Yin-like",disclosure:"Simulation",status:"awaiting_answer",pitch_text:"Pitch",pitch_sha256:"x",turns:[],annotations:[],evidence:[],usage:{},findings:[],max_questions:3,conversation:[{question_id:"q1",question:"What proves **repeatability**?",response_comment:"Your **traction** is early.",rationale_labels:["traction_repeatability_concern"],founder_answer:"We have **three renewals**."}],active_question:{question_id:"q2",text:"What is the **gross margin**?",rationale_labels:["unit_economics_assessment"]}} satisfies Session;
    render(<><ConversationPanel session={session} busy={false} onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/><EvidenceDrawer evidence={[{evidence_id:"e1",source_kind:"pitch",source_path:"pitch.md",excerpt:"> **Founder-provided** evidence"}]} onClose={vi.fn()}/></>);
    expect(screen.getByText("repeatability").tagName).toBe("STRONG");
    expect(screen.getByText("three renewals").tagName).toBe("STRONG");
    expect(screen.getByText("Founder-provided").closest("blockquote")).not.toBeNull();
  });
});
