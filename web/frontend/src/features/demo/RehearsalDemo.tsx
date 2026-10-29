import { useState } from 'react';
import { InvestorPortrait } from '../../components/InvestorPortrait';
import { ScoreTrajectory } from '../../components/ScoreTrajectory';
import './demo.css';

const original = 'RelayDesk helps independent service businesses fill cancelled appointments. We have 30 paying customers and $18,000 MRR, with strong retention. We are raising $750,000 to grow sales and expand across the country.';
const revised = 'RelayDesk helps independent service businesses fill cancelled appointments. Today, 18 businesses pay $12,000 in subscription MRR; another 12 are in paid pilots generating $6,000 this month, which we exclude from MRR. Our 12-customer, twelve-month subscription cohort has 107% net revenue retention. Two existing subscription customers have signed expansions worth $2,000 additional MRR starting next month; that revenue is not yet live. We are raising $750,000 to convert pilots and test a repeatable sales process in two cities before expanding nationally. Pilot conversion and acquisition cost remain the main risks.';
const investors = [
  {name:'Investor #1',score:54,focus:'Market opportunity',positive:'A clear operational problem and recurring workflow.',concern:'The expansion plan is broader than the evidence supports.'},
  {name:'Investor #2',score:68,focus:'Early revenue and retention',positive:'Paying users and a measurable retention opportunity.',concern:'Revenue quality and retention cohorts need verification.'},
  {name:'Investor #3',score:41,focus:'Repeatable distribution',positive:'A product with a defined business customer.',concern:'Acquisition cost and a scalable sales channel are unproven.'},
];
const exchanges = [
  {question:'When you say strong retention, which customers and time period do you mean?',answer:'Our twelve-month cohort contains 12 subscription customers. Its net revenue retention is 107%. That includes expansion, so it does not establish logo retention for all 30 accounts.',score:74,rationale:'Traction validation',assessment:'A defined cohort supports retention. The small sample and missing logo-retention figure remain limitations.',change:'Replace “strong retention” with the cohort size, time window, and exact metric.'},
  {question:'Is all $18,000 recurring subscription revenue, or does it include pilots?',answer:'Only $12,000 is subscription MRR from 18 customers. The remaining $6,000 is this month’s fees from 12 paid pilots. We should not have described the full amount as MRR.',score:61,rationale:'Revenue quality',assessment:'The clarification lowers estimated fit: recurring revenue is one-third below the original claim. Pilot conversion is still uncertain.',change:'Separate subscription MRR from pilot fees; distinguish subscription customers from pilot accounts.'},
  {question:'What evidence supports expansion, and what will this round actually prove?',answer:'Two existing subscription customers signed expansions adding $2,000 MRR next month. That is contracted, not live revenue. We will use the $750,000 round to convert pilots and validate repeatable sales in two cities; we do not yet have reliable acquisition-cost data.',score:72,rationale:'Capital efficiency and execution',assessment:'Signed expansion and a narrower use of funds improve fit. The score does not assume pilot conversions or a proven sales channel.',change:'Label contracted revenue separately and replace nationwide growth with measurable, staged milestones.'},
];

export function RehearsalDemo() {
  const [step, setStep] = useState(0);
  const current = step ? exchanges[step - 1].score : 68;
  return <section className="rehearsal-demo">
    <header className="demo-heading">
      <p className="demo-label">Fictional demonstration · No model calls</p>
      <h1>One pitch. Three investors. A sharper story.</h1>
      <p>All investors, company facts, answers, and scores below are invented for demonstration. Scores illustrate model fit, not real investment probabilities.</p>
      <div className="demo-controls"><button className="button" onClick={() => setStep(3)}>Show complete example</button><button className="button secondary" onClick={() => setStep(0)}>Reset example</button></div>
    </header>

    <section aria-labelledby="demo-original"><span className="demo-label">01 / Initial pitch</span><h2 id="demo-original">RelayDesk · Version 1</h2><p className="demo-pitch">{original}</p></section>
    <section aria-labelledby="demo-comparison"><span className="demo-label">02 / Compare three investors</span><h2 id="demo-comparison">Who is the strongest initial fit?</h2>
      <div className="demo-investors">{investors.map((investor,index) => <article key={investor.name} className={index === 1 ? 'demo-investor selected' : 'demo-investor'}>
        <InvestorPortrait name={investor.name} src="/investor-placeholder.svg" alt={`${investor.name} placeholder`} />
        <h3>{investor.name}</h3><p>{investor.focus}</p><strong className="demo-score">{investor.score}<small>/100 initial fit</small></strong>
        {index === 1 && <p className="demo-winner">Selected for follow-up · Highest initial fit</p>}
        <dl><dt>Positive signal</dt><dd>{investor.positive}</dd><dt>Open concern</dt><dd>{investor.concern}</dd></dl>
      </article>)}</div>
      <p>Investor #2 is selected because 68 is the highest initial score. Investors #1 and #3 are not reassessed during this example.</p>
    </section>

    <section aria-labelledby="demo-rehearsal"><span className="demo-label">03 / Expand with Investor #2</span><h2 id="demo-rehearsal">Questions turn claims into evidence</h2>
      <ScoreTrajectory initial={.68} current={current / 100} />
      <p className="demo-progress" aria-live="polite">{step} of 3 scripted exchanges revealed · Current illustrative fit: {current}/100</p>
      {exchanges.slice(0, step).map((exchange,index) => <article className="demo-exchange" key={exchange.question}>
        <header><h3>Question {index + 1} · {exchange.rationale}</h3><strong>{index ? exchanges[index - 1].score : 68} → {exchange.score}/100</strong></header>
        <p><b>Investor #2:</b> {exchange.question}</p><p><b>Founder:</b> {exchange.answer}</p>
        <p className="demo-assessment"><b>Illustrative reassessment:</b> {exchange.assessment}</p><p><b>Pitch change:</b> {exchange.change}</p>
      </article>)}
      {step < exchanges.length && <button className="button" onClick={() => setStep(value => value + 1)}>{step ? 'Reveal next question and answer' : 'Begin rehearsal with Investor #2'}</button>}
    </section>

    {step === 3 && <section aria-labelledby="demo-revision"><span className="demo-label">04 / Revise the pitch</span><h2 id="demo-revision">More precise, not simply more optimistic</h2>
      <div className="demo-revisions"><article><h3>Before · Version 1</h3><p>{original}</p></article><article><h3>After · Version 2</h3><p>{revised}</p></article></div>
      <p>The follow-up evidence moves Investor #2 from 68 to 72, including a drop to 61 when the revenue claim is corrected. Version 2 captures those answers; rewriting the pitch does not itself generate another score increase.</p>
      <p><b>Still unresolved:</b> pilot conversion, acquisition cost, and retention beyond the small reported cohort. In a real workflow, save Version 2 and reassess all three investors against the same revised pitch before making another comparison.</p>
    </section>}
  </section>;
}
