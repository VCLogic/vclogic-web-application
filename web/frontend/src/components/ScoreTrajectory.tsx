import { fitScore } from "./AssessmentSemantics";

export function ScoreTrajectory({initial,current}:{initial:number;current:number}) {
  const before=fitScore(initial)??0;
  const after=fitScore(current)??0;
  const delta=after-before;
  return <div className="score-trajectory" aria-label={`Estimated investor fit moved from ${before} to ${after} out of 100`}>
    <div><span>Initial fit</span><strong>{before}/100</strong></div><i/>
    <div><span>Current fit</span><strong>{after}/100</strong></div>
    <b className={delta>=0?"up":"down"}>{delta>=0?"+":""}{delta} points</b>
  </div>;
}
