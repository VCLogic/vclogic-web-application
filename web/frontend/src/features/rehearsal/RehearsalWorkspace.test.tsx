import { cleanup,render,screen,waitFor } from "@testing-library/react";import userEvent from "@testing-library/user-event";import { QueryClient,QueryClientProvider } from "@tanstack/react-query";import { MemoryRouter,Route,Routes } from "react-router-dom";import { afterEach,expect,it,vi } from "vitest";import { api,ApiError } from "../../api/client";import type { Session } from "../../api/types";import { AssessmentPanel } from "./AssessmentPanel";import { ConversationPanel } from "./ConversationPanel";import { PitchPanel } from "./PitchPanel";import { RehearsalExperience,RehearsalWorkspace } from "./RehearsalWorkspace";import { WorkspaceTabs } from "./WorkspaceTabs";
vi.mock("../../api/events",()=>({subscribeToSession:vi.fn(()=>()=>{})}));
afterEach(()=>{cleanup();vi.restoreAllMocks()});
const session:Session={session_id:"s1",vc_slug:"charles",investor_display_name:"Charles Hudson-like Investor",disclosure:"Not the real investor.",status:"awaiting_answer",rehearsal_depth:"standard",pitch_text:"We have ten paying customers and uncertain retention.",pitch_sha256:"abc",initial_assessment:{decision:"Out",investment_likelihood:.4,decision_confidence:.7,rationale_counts:{negative:1},decision_justification:"Retention remains unclear."},current_assessment:{decision:"Out",investment_likelihood:.52,decision_confidence:.72,review_priority_score:.6,rationale_counts:{positive:1,negative:1},decision_justification:"Evidence improved, but uncertainty remains.",score_reconciliation:"The final synthesis increased likelihood by 12 percentage points because the new evidence outweighed the remaining concerns."},active_question:{question_id:"q2",text:"How many customers renewed?",response_comment:"Ten customers is a start; I need to understand whether they stay.",rationale_labels:["traction_validation"],decision_relevance:"Retention could change the decision."},conversation:[{question_id:"q1",question:"Who is using the product?",response_comment:"Let’s begin with customer evidence.",rationale_labels:["customer_validation"],founder_answer:"Founder-provided answer",evidence_effect:"clarification",investment_likelihood_before:.4,investment_likelihood_after:.4,likelihood_delta:0}],max_questions:5,turns:[{text:"Founder-provided answer"}],annotations:[{annotation_id:"a1",start:8,end:28,text:"ten paying customers",direction:"positive",rationale_ids:["traction_validation"],evidence_ids:["e1"]}],evidence:[{evidence_id:"e1",source_kind:"pitch",source_path:"pitch.txt",excerpt:"ten paying customers"}],usage:{},findings:[]};
it("presents evidence-responsive pitch meeting and decision regions",async()=>{const user=userEvent.setup();const evidence=vi.fn();render(<><PitchPanel session={session} onEvidence={evidence}/><ConversationPanel session={session} busy={false} onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/><AssessmentPanel initial={session.initial_assessment} current={session.current_assessment} onEvidence={evidence}/><WorkspaceTabs active="pitch" onChange={vi.fn()}/></>);expect(screen.getByText("Initial assessment")).toBeVisible();expect(screen.getByText("Current assessment")).toBeVisible();expect(screen.getByText("Leans Out")).toBeVisible();expect(screen.getByText("+12 points")).toBeVisible();expect(screen.getByRole("status")).toHaveTextContent(/increased estimated investor fit by 12 points/i);expect(screen.getByText("Current-pitch rationales")).toBeVisible();expect(screen.getByRole("button",{name:/negative pitch signals/i})).toBeVisible();expect(screen.getAllByText(/founder-provided evidence/i)).toHaveLength(1);expect(screen.queryByText(/clarified · no score change/i)).not.toBeInTheDocument();await user.click(screen.getByText("ten paying customers"));expect(evidence).toHaveBeenCalledWith(["e1"]);expect(screen.getByRole("tab",{name:"Assessment"})).toBeVisible()});

it("keeps legacy assessments usable when score reconciliation is absent",()=>{
 const legacy={...session.current_assessment!,score_reconciliation:undefined};
 render(<AssessmentPanel initial={session.initial_assessment} current={legacy} onEvidence={vi.fn()}/>);
 expect(screen.queryByText(/final synthesis increased likelihood/i)).not.toBeInTheDocument();
 expect(screen.getByText("Current assessment")).toBeVisible();
});

it("shows an optimistic founder exchange until the server advances",async()=>{
 const user=userEvent.setup();const answer=vi.fn();
 const view=render(<ConversationPanel session={session} busy={false} activityStage="awaiting_answer" onAnswer={answer} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 const composer=view.getByRole("textbox",{name:"Your answer"});
 await user.type(composer,"Twelve-month retention is 82%.");
 await user.click(view.getByRole("button",{name:/submit evidence/i}));
 expect(answer).toHaveBeenCalledWith("Twelve-month retention is 82%.");
 expect(view.getByText("Twelve-month retention is 82%.")).toBeVisible();
 expect(view.getByRole("status")).toHaveTextContent(/submitting your evidence/i);
 expect(view.getByRole("button",{name:/submit evidence/i})).toBeDisabled();

 view.rerender(<ConversationPanel session={session} busy={false} activityStage="answer_update_running" onAnswer={answer} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(view.getByRole("status")).toHaveTextContent(/reviewing your evidence/i);

 const advanced={...session,turns:[...session.turns,{text:"Twelve-month retention is 82%."}],conversation:[...session.conversation!,{question_id:"q2",question:"How many customers renewed?",rationale_labels:["traction_validation"],founder_answer:"Twelve-month retention is 82%."}],active_question:{...session.active_question!,question_id:"q3",text:"What drove renewals?"}};
 view.rerender(<ConversationPanel session={advanced} busy={false} activityStage="awaiting_answer" onAnswer={answer} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(view.getByText("What drove renewals?")).toBeVisible();
 expect(view.queryByRole("status")).not.toBeInTheDocument();
});

it("retains the submitted answer and offers retry after a failed cycle",async()=>{
 const user=userEvent.setup();const retry=vi.fn();
 const view=render(<ConversationPanel session={session} busy={false} activityStage="awaiting_answer" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={retry}/>);
 await user.type(view.getByRole("textbox",{name:"Your answer"}),"Evidence that must not disappear.");
 await user.click(view.getByRole("button",{name:/submit evidence/i}));
 view.rerender(<ConversationPanel session={session} busy={false} activityStage="failed" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={retry}/>);
 expect(view.getByText("Evidence that must not disappear.")).toBeVisible();
 expect(view.getByRole("alert")).toHaveTextContent(/could not finish reviewing/i);
 await user.click(view.getByRole("button",{name:/retry review/i}));
 expect(retry).toHaveBeenCalledOnce();
});

it("renders a natural rationale-backed chat turn",()=>{
 render(<ConversationPanel session={session} busy={false} onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(screen.getByText("Ten customers is a start; I need to understand whether they stay.")).toBeVisible();
 expect(screen.getByText("How many customers renewed?")).toBeVisible();
 expect(screen.getByText("Traction validation")).toBeVisible();
 expect(screen.getByText("Question 2 · Standard rehearsal")).toBeVisible();
 expect(screen.queryByText(/Clarified · no score change/i)).not.toBeInTheDocument();
 expect(screen.queryByText("Why this matters")).not.toBeInTheDocument();
});

it("does not clear a pending answer merely because the question changes",async()=>{
 const user=userEvent.setup();
 const view=render(<ConversationPanel session={session} busy={false} activityStage="awaiting_answer" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 await user.type(view.getByRole("textbox",{name:"Your answer"}),"Exact evidence that must be acknowledged.");
 await user.click(view.getByRole("button",{name:/submit evidence/i}));
 view.rerender(<ConversationPanel session={{...session,active_question:{...session.active_question!,question_id:"q3",text:"A premature next question"}}} busy={false} activityStage="continuation_running" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(view.getByText("Exact evidence that must be acknowledged.")).toBeVisible();
 expect(view.getByRole("status")).toBeVisible();
});

it("does not accept a server turn whose answer digest conflicts",async()=>{
 vi.stubGlobal("crypto",{subtle:{digest:async()=>new Uint8Array(32).fill(1).buffer}});
 const user=userEvent.setup();
 const view=render(<ConversationPanel session={session} busy={false} activityStage="awaiting_answer" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 await user.type(view.getByRole("textbox",{name:"Your answer"}),"Exact founder evidence.");
 await user.click(view.getByRole("button",{name:/submit evidence/i}));
 const conflicted={...session,conversation:[...session.conversation!,{question_id:"q2",question:session.active_question!.text,rationale_labels:["traction_validation"],founder_answer:"Exact founder evidence.",answer_sha256:"0".repeat(64)}]};
 view.rerender(<ConversationPanel session={conflicted} busy={false} activityStage="awaiting_answer" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(await view.findByRole("alert")).toHaveTextContent(/could not verify the returned answer/i);
 expect(view.getByText("Exact founder evidence.")).toBeVisible();
 vi.unstubAllGlobals();
});

it("allows founders to finish only after one answer has been accepted",()=>{
 const unanswered={...session,conversation:[],turns:[]};
 const view=render(<ConversationPanel session={unanswered} busy={false} onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(view.getByRole("button",{name:/finish and assess now/i})).toBeDisabled();
 view.rerender(<ConversationPanel session={session} busy={false} onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()}/>);
 expect(view.getByRole("button",{name:/finish and assess now/i})).toBeEnabled();
});

it("hides provisional analysis but keeps the immutable pitch accessible during conversation",async()=>{
 const user=userEvent.setup();
 render(<RehearsalExperience session={session} busy={false} stage="awaiting_answer" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()} onEvidence={vi.fn()}/>);
 expect(screen.getByRole("textbox",{name:"Your answer"})).toBeVisible();
 expect(screen.queryByText("Initial assessment")).not.toBeInTheDocument();
 expect(screen.queryByText("Current assessment")).not.toBeInTheDocument();
 expect(screen.queryByText("Pitch evidence")).not.toBeInTheDocument();
 expect(screen.getByRole("tablist")).toBeVisible();
 expect(screen.queryByRole("tab",{name:"Assessment"})).not.toBeInTheDocument();
 await user.click(screen.getByRole("tab",{name:"Pitch & evidence"}));
 expect(screen.getByText("ten paying customers")).toBeVisible();
});

it("unlocks post-session coaching and explains why generic questioning ended",async()=>{
 const user=userEvent.setup();
 const complete:Session={...session,status:"complete",active_question:undefined,closing_message:"We've reached the end of our available questions, so I'll assess the pitch."};
 render(<RehearsalExperience session={complete} busy={false} stage="complete" onAnswer={vi.fn()} onFinish={vi.fn()} onRetry={vi.fn()} onEvidence={vi.fn()}/>);
 expect(screen.getByRole("tab",{name:"Conversation"})).toBeVisible();
 expect(screen.getByText(/remaining uncertainties require evidence or milestones/i)).toBeVisible();
 expect(screen.queryByText("Initial assessment")).not.toBeInTheDocument();
 await user.click(screen.getByRole("tab",{name:"Assessment"}));
 expect(screen.getByText("Initial assessment")).toBeVisible();
 await user.click(screen.getByRole("tab",{name:"Pitch & evidence"}));
 expect(screen.getByText("ten paying customers")).toBeVisible();
});

it("describes completed-session integrity without implying claim verification",async()=>{
 const complete:Session={...session,status:"complete",active_question:undefined};
 vi.spyOn(api,"session").mockResolvedValue(complete);
 vi.spyOn(api,"profile").mockResolvedValue({investor:{vc_slug:"charles",display_name:"Charles Hudson-like Investor",firm:"Precursor",role:"Partner",disclosure:"Not the real investor.",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},sections:[]});
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={["/sessions/s1"]}><Routes><Route path="/sessions/:sessionId" element={<RehearsalWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);
 const integrity=await screen.findByText("Assessment integrity checked");
 expect(integrity).toHaveAttribute("title",expect.stringMatching(/founder claims were not independently fact-checked/i));
 expect(screen.queryByText("Artifacts verified")).not.toBeInTheDocument();
});

it("refreshes an accepted answer until the next question is visible without a page reload",async()=>{
 const user=userEvent.setup();
 const advanced:Session={...session,active_question:{...session.active_question!,question_id:"q3",text:"What drove renewals?"},conversation:[...session.conversation!,{question_id:"q2",question:session.active_question!.text,rationale_labels:["traction_validation"],founder_answer:"Twelve-month retention is 82%.",evidence_effect:"new_positive",investment_likelihood_before:.52,investment_likelihood_after:.6,likelihood_delta:.08}],turns:[...session.turns,{text:"Twelve-month retention is 82%."}]};
 const sessionCall=vi.spyOn(api,"session").mockResolvedValueOnce(session).mockResolvedValueOnce(session).mockResolvedValue(advanced);
 vi.spyOn(api,"profile").mockResolvedValue({investor:{vc_slug:"charles",display_name:"Charles Hudson-like Investor",firm:"Precursor",role:"Partner",disclosure:"Not the real investor.",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},sections:[]});
 vi.spyOn(api,"answer").mockResolvedValue({session_id:"s1",event_url:"/events"});
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={["/sessions/s1"]}><Routes><Route path="/sessions/:sessionId" element={<RehearsalWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);
 expect(await screen.findByText("How many customers renewed?")).toBeVisible();
 await user.type(screen.getByRole("textbox",{name:"Your answer"}),"Twelve-month retention is 82%.");
 await user.click(screen.getByRole("button",{name:/submit evidence/i}));
 await waitFor(()=>expect(api.answer).toHaveBeenCalledOnce());
 expect(await screen.findByText("What drove renewals?",{}, {timeout:3500})).toBeVisible();
 expect(sessionCall.mock.calls.length).toBeGreaterThanOrEqual(3);
});

it("restores the processing lock from the server after a page refresh",async()=>{
 const activeSession:Session={...session,operation_active:true};
 vi.spyOn(api,"session").mockResolvedValue(activeSession);
 vi.spyOn(api,"profile").mockResolvedValue({investor:{vc_slug:"charles",display_name:"Charles Hudson-like Investor",firm:"Precursor",role:"Partner",disclosure:"Not the real investor.",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},sections:[]});
 const answer=vi.spyOn(api,"answer");
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={["/sessions/s1"]}><Routes><Route path="/sessions/:sessionId" element={<RehearsalWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);

 expect(await screen.findByText("How many customers renewed?")).toBeVisible();
 expect(screen.getByRole("textbox",{name:"Your answer"})).toBeDisabled();
 expect(screen.getByRole("button",{name:/submit evidence/i})).toBeDisabled();
 expect(answer).not.toHaveBeenCalled();
});

it("keeps polling instead of exposing a raw session-busy conflict",async()=>{
 const user=userEvent.setup();
 vi.spyOn(api,"session").mockResolvedValue(session);
 vi.spyOn(api,"profile").mockResolvedValue({investor:{vc_slug:"charles",display_name:"Charles Hudson-like Investor",firm:"Precursor",role:"Partner",disclosure:"Not the real investor.",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},sections:[]});
 vi.spyOn(api,"answer").mockRejectedValue(new ApiError(409,"session mutation already active: s1","session_busy"));
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={["/sessions/s1"]}><Routes><Route path="/sessions/:sessionId" element={<RehearsalWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);

 await user.type(await screen.findByRole("textbox",{name:"Your answer"}),"Evidence already submitted.");
 await user.click(screen.getByRole("button",{name:/submit evidence/i}));

 expect(await screen.findByText(/response is already being processed/i)).toBeVisible();
 expect(screen.queryByText(/session mutation already active/i)).not.toBeInTheDocument();
 expect(screen.getByRole("button",{name:/submit evidence/i})).toBeDisabled();
});
