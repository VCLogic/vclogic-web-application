import { fitScore } from "./AssessmentSemantics";

export function DecisionGauge({value,label="Estimated investor fit"}:{value:number;label?:string}) {
  const score=fitScore(value)??0;
  return <div className="decision-gauge" aria-label={`${label}, ${score} out of 100`}>
    <div className="gauge-value"><strong>{score}/100</strong><span>{label}</span></div>
    <div className="gauge-track"><i style={{width:`${score}%`}}/></div>
  </div>;
}
