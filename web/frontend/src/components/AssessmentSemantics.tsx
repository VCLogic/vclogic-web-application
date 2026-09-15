export type AssessmentMetricKind = "fit" | "confidence" | "percentile";

export function decisionLean(decision?: string | null): string {
  if (decision?.toLowerCase() === "in") return "Leans In";
  if (decision?.toLowerCase() === "out") return "Leans Out";
  return "Assessment unavailable";
}

export function fitScore(value?: number | null): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.round(Math.min(1, Math.max(0, value)) * 100);
}

export function founderSafeAssessmentText(text?: string | null): string {
  return (text || "")
    .replace(/estimated investment likelihood/gi, "estimated investor fit")
    .replace(/investment likelihood/gi, "estimated investor fit")
    .replace(/\blikelihood\b/gi, "estimated investor fit")
    .replace(/percentage points/gi, "points");
}

const explanations: Record<AssessmentMetricKind, string> = {
  fit: "Alignment with this investor-like model's observable decision logic—not the probability that the real investor will invest.",
  confidence: "How strongly the available evidence supports the model's current decision.",
  percentile: "How this pitch compares with historical pitches evaluated for this investor-like model.",
};

export function AssessmentMetricHelp({ kind }: { kind: AssessmentMetricKind }) {
  return <span className="metric-help">{explanations[kind]}</span>;
}
