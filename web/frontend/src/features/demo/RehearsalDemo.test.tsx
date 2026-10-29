import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { RehearsalDemo } from './RehearsalDemo';

afterEach(() => {cleanup(); vi.unstubAllGlobals();});

it('compares three fictional investors and reveals a non-monotonic rehearsal and revised pitch without API calls', () => {
  const fetch=vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<RehearsalDemo/>);
  expect(screen.getByText(/All investors, company facts, answers, and scores/)).toBeVisible();
  expect(screen.getAllByRole('img')).toHaveLength(3);
  expect(screen.getByText('Selected for follow-up · Highest initial fit')).toBeVisible();
  expect(screen.queryByText('After · Version 2')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Begin rehearsal with Investor #2'}));
  expect(screen.getByText('68 → 74/100')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Reveal next question and answer'}));
  expect(screen.getByText('74 → 61/100')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Reveal next question and answer'}));
  expect(screen.getByText('61 → 72/100')).toBeVisible();
  expect(screen.getByText('After · Version 2')).toBeVisible();
  expect(screen.getByText(/rewriting the pitch does not itself generate another score increase/)).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Reset example'}));
  expect(screen.queryByText('After · Version 2')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Show complete example'}));
  expect(screen.getByText('After · Version 2')).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
});
