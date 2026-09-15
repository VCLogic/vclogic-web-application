export interface CaseIndexItem { id: string; label: string; meta?: string }

export function CaseIndex({ label, items, active, onChange }: {
  label: string; items: CaseIndexItem[]; active: string; onChange: (id: string) => void;
}) {
  return <nav className="case-index" aria-label={label}>
    <span className="case-index-title">{label}</span>
    <ol>{items.map((item, index) => <li key={item.id}>
      <button type="button" aria-label={item.label} aria-current={active === item.id ? "page" : undefined} onClick={() => onChange(item.id)}>
        <span className="case-index-number">{String(index + 1).padStart(2, "0")}</span>
        <span>{item.label}</span>
        {item.meta&&<small>{item.meta}</small>}
      </button>
    </li>)}</ol>
  </nav>;
}
