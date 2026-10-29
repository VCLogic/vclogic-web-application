import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { InvestorPortrait } from '../../components/InvestorPortrait';
import { ScoreTrajectory } from '../../components/ScoreTrajectory';
import { SafeMarkdown } from '../../components/SafeMarkdown';
import './demo.css';

type RecordedRun = {
  company:string; recorded_at:string; pitch_sha256:string; initial_pitch:string;
  investors:{name:string;firm:string;score:number;decision:string;positives:string[];concerns:string[];justification:string}[];
  selected:number; exchanges:{question:string;answer:string;rationale_labels:string[];before:number;after:number;impact:string}[];
  final_score:number;final_decision:string;final_justification:string;recommendations:string[];revised_pitch:string;revision_note:string;
};
const score = (value:number) => Math.round(value * 100);
const label = (value:string) => value.replaceAll('_',' ');

export function RecordedRehearsalDemo() {
  const [step,setStep] = useState(0);
  const {data,error,isPending} = useQuery({queryKey:['recorded-demo'],queryFn:async():Promise<RecordedRun> => {
    const response=await fetch('/api/demo/recorded');
    if (!response.ok) throw new Error('The recorded example has not been installed. Export a verified rehearsal into this workspace first.');
    return response.json();
  }});
  if(isPending)return <p className="rehearsal-demo" role="status">Opening recorded rehearsal…</p>;
  if(error || !data)return <section className="rehearsal-demo"><h1>Recorded rehearsal unavailable</h1><p role="alert">{error?.message}</p><Link to="/demo/fictional">Open the fictional example</Link></section>;
  const winner=data.investors[data.selected];
  const tied=data.investors.filter(investor=>investor.score===winner.score).length>1;
  const complete=step===data.exchanges.length+1;
  const current=complete ? data.final_score : step ? data.exchanges[step-1].after : winner.score;
  return <section className="rehearsal-demo">
    <header className="demo-heading"><p className="demo-label">Anonymous mode · Recorded model run · {data.recorded_at.slice(0,10)}</p>
      <h1>{data.company}: three investors, one rehearsal</h1>
      <p>These are existing model results for a demo pitch, replayed from verified local artifacts. Investor and firm identities are replaced. They are not fresh assessments against the latest Investment Memories or predictions of real investment.</p>
      <div className="demo-controls"><button className="button" onClick={()=>setStep(data.exchanges.length+1)}>Show complete run</button><button className="button secondary" onClick={()=>setStep(0)}>Restart replay</button><Link to="/?anonymous=1">Browse anonymously</Link></div>
    </header>
    <section><span className="demo-label">01 / Same pitch for all three investors</span><h2>Initial {data.company} pitch</h2><details><summary>Read the original pitch</summary><SafeMarkdown>{data.initial_pitch}</SafeMarkdown></details><p>All three assessment artifacts and the rehearsal were checked against the same pitch SHA-256 before export.</p></section>
    <section><span className="demo-label">02 / Initial comparison</span><h2>{tied?'Joint-highest initial fit':'Highest initial fit'}: {winner.name}</h2>
      <div className="demo-investors">{data.investors.map((investor,index)=><article key={investor.name} className={`demo-investor${index===data.selected?' selected':''}`}>
        <InvestorPortrait name={investor.name} src="/investor-placeholder.svg" alt={`${investor.name} placeholder`}/><h3>{investor.name}</h3><p>{investor.firm}</p>
        <strong className="demo-score">{score(investor.score)}<small>/100 initial fit</small></strong><p>Recorded decision: {investor.decision}</p>
        {index===data.selected&&<p className="demo-winner">Selected for deeper rehearsal{tied?' · Tied highest initial score':''}</p>}
        <dl><dt>Positive signals</dt><dd>{investor.positives.map(label).join(' · ')||'None recorded'}</dd><dt>Concerns</dt><dd>{investor.concerns.map(label).join(' · ')||'None recorded'}</dd></dl>
        <details><summary>Read recorded assessment</summary><SafeMarkdown>{investor.justification}</SafeMarkdown></details>
      </article>)}</div>
      <p>Fit is an estimated model judgment, not a calibrated probability. Only {winner.name} is updated below; the other two scores remain their initial results.</p>
    </section>
    <section><span className="demo-label">03 / Questions, recorded answers, and impact</span><h2>Rehearsal with {winner.name}</h2><ScoreTrajectory initial={winner.score} current={current}/>
      <p aria-live="polite">{Math.min(step,data.exchanges.length)} of {data.exchanges.length} recorded answers shown{complete?' · Final synthesis shown':''}.</p>
      {data.exchanges.slice(0,step).map((turn,index)=><article className="demo-exchange" key={index}>
        <header><h3>Question {index+1} · {turn.rationale_labels.map(label).join(', ')}</h3><strong>{score(turn.before)} → {score(turn.after)}/100</strong></header>
        <p><b>{winner.name}:</b> {turn.question}</p><div><b>Recorded founder answer</b><SafeMarkdown>{turn.answer}</SafeMarkdown></div><p className="demo-assessment"><b>Recorded impact:</b> {turn.impact}</p>
      </article>)}
      {!complete&&<button className="button" onClick={()=>setStep(value=>value+1)}>{step===data.exchanges.length?'Show final synthesis and pitch changes':step?'Reveal next recorded exchange':'Start recorded rehearsal'}</button>}
      {complete&&<article className="demo-exchange"><h3>Final synthesis · {score(data.exchanges.at(-1)!.after)} → {score(data.final_score)}/100</h3><p>Recorded final decision: <b>{data.final_decision}</b>. This final synthesis is separate from the per-answer updates.</p><SafeMarkdown>{data.final_justification}</SafeMarkdown></article>}
    </section>
    {complete&&<section><span className="demo-label">04 / Impact on the pitch</span><h2>What to change—and what remains unproven</h2><ol>{data.recommendations.map(value=><li key={value}><p>{value}</p></li>)}</ol>
      <p><b>{data.revision_note}</b></p><div className="demo-revisions"><article><h3>Original pitch</h3><SafeMarkdown>{data.initial_pitch}</SafeMarkdown></article><article><h3>Revision draft with recorded clarifications</h3><SafeMarkdown>{data.revised_pitch}</SafeMarkdown></article></div>
      <p>The original saved pitch and source run remain unchanged. The revision draft is not a new assessment and has no new model score.</p>
    </section>}
  </section>;
}
