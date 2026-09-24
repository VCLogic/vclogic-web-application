type VCLogicMarkProps = { className?: string };

export function VCLogicMark({ className = "" }: VCLogicMarkProps) {
  const classes = ["vc-logic-mark", className].filter(Boolean).join(" ");

  return <svg className={classes} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <path className="vc-logic-mark__frame" d="M13 5H7L2.5 16 7 27h6M19 5h6l4.5 11L25 27h-6" />
    <path className="vc-logic-mark__path" d="m10 20 6-8 6 7" />
    <circle cx="10" cy="20" r="2" />
    <circle cx="16" cy="12" r="2" />
    <circle cx="22" cy="19" r="2" />
  </svg>;
}
