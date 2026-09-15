import { AlertCircle, CircleHelp, TrendingUp } from "lucide-react";

type Props = {
  positive?: string[];
  negative?: string[];
  unresolved?: string[];
  positiveCounts?: Record<string, number> | null;
  negativeCounts?: Record<string, number> | null;
  unresolvedCounts?: Record<string, number> | null;
  dark?: boolean;
};

const formatLabel = (value: string) => value
  .replaceAll("_", " ")
  .replace(/\b\w/g, character => character.toUpperCase());

const observedCount = (counts: Record<string, number> | null | undefined, value: string): number | undefined => {
  const count = counts?.[value];
  return typeof count === "number" && Number.isInteger(count) && count > 0 ? count : undefined;
};

export function DecisionInfluenceSummary({
  positive = [],
  negative = [],
  unresolved = [],
  positiveCounts,
  negativeCounts,
  unresolvedCounts,
  dark = false,
}: Props) {
  const influences = [
    { direction: "positive", label: "Creates conviction", values: positive, counts: positiveCounts, Icon: TrendingUp },
    { direction: "negative", label: "Creates concern", values: negative, counts: negativeCounts, Icon: AlertCircle },
    { direction: "unresolved", label: "Mixed / conditional", values: unresolved, counts: unresolvedCounts, Icon: CircleHelp },
  ].filter(influence => influence.values.length > 0).map(influence => ({
    ...influence,
    value: influence.values[0],
    count: observedCount(influence.counts, influence.values[0]),
  }));

  if (!influences.length) return null;
  const displayedMaximum = Math.max(
    0,
    ...influences.flatMap(influence => influence.count === undefined ? [] : [influence.count]),
  );

  return <section className={`decision-influence-summary${dark ? " decision-influence-summary--dark" : ""}`} aria-label="Frequently observed rationales">
    {influences.map(({ direction, label, value, count, Icon }) => {
      const normalizedPercent = count === undefined ? undefined : Math.round(count / displayedMaximum * 100);
      const formattedValue = formatLabel(value);
      return <div className={`decision-influence-row ${direction}`} key={direction}>
        <Icon aria-hidden="true" size={16} />
        <span className="decision-influence-label">{label}</span>
        <div className="decision-influence-content">
          <span
            className="decision-influence-rationale"
            aria-label={count === undefined ? `${formattedValue}; observed recurrence unavailable` : undefined}
          >{formattedValue}</span>
          {count !== undefined && <div
            className="decision-influence-meter"
            role="meter"
            aria-label={`${formattedValue} observed recurrence frequency, not confidence or importance`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={normalizedPercent}
            aria-valuetext={`${count} observed activations; ${normalizedPercent}% of displayed maximum.`}
          >
            <span className="decision-influence-meter-fill" style={{ width: `${normalizedPercent}%` }} />
          </div>}
        </div>
      </div>;
    })}
  </section>;
}
