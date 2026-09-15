export type ProgressEvent={event_id:number;session_id:string;stage:string;payload:Record<string,unknown>};
export function subscribeToSession(url:string,onEvent:(event:ProgressEvent)=>void,onError?:(event:Event)=>void){
 const source=new EventSource(url); const stages=["queued","preparing_inputs","phase1_running","phase2_running","rehearsal_running","answer_update_running","continuation_running","question_selection_running","decision_synthesis_running","founder_feedback_running","awaiting_answer","finished","complete","failed"];
 stages.forEach(stage=>source.addEventListener(stage,event=>{const parsed=JSON.parse((event as MessageEvent).data);onEvent(parsed);if(stage==="complete"||stage==="failed")source.close()})); source.onerror=event=>onError?.(event); return()=>source.close();
}
