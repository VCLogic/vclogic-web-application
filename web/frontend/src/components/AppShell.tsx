import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { InvestorLensMark } from "./InvestorLensMark";

export function AppShell({ children }: { children: ReactNode }) {
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="app-header">
      <NavLink className="wordmark" to="/" aria-label="InvestorLens home">
        <InvestorLensMark />
        <span className="wordmark-text"><span>Investor</span>Lens</span>
      </NavLink>
      <nav className="primary-nav" aria-label="Primary navigation">
        <NavLink to="/" end>Investors</NavLink>
        <NavLink to="/pitches">My Pitches</NavLink>
        <NavLink to="/sessions">Rehearsals</NavLink>
      </nav>
      <p className="header-method">Evidence-grounded decision rehearsal</p>
    </header>
    <main id="main-content">{children}</main>
  </div>;
}
