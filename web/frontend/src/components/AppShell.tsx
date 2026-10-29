import { screenshotMode } from "../api/screenshotMode";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { VCLogicMark } from "./VCLogicMark";

export function AppShell({ children }: { children: ReactNode }) {
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="app-header">
      <NavLink className="wordmark" to="/" aria-label="VCLogic home">
        <VCLogicMark />
        <span className="wordmark-text"><span>VC</span>Logic</span>
      </NavLink>
      <nav className="primary-nav" aria-label="Primary navigation">
        <NavLink to="/" end>Investors</NavLink>
        <NavLink to="/pitches">My Pitches</NavLink>
        <NavLink to="/sessions">Rehearsals</NavLink>
        <NavLink to="/settings/investors">Settings</NavLink>
      </nav>
      <p className="header-method screenshot-mode-status">{screenshotMode() ? <a href="/?anonymous=0">Exit</a> : <a href="/?anonymous=1">Anonymize</a>}</p>
    </header>
    <main id="main-content">{children}</main>
  </div>;
}
