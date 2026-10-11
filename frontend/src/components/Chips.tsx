/** A labelled row of small chips: what someone wants to see, who needs something, who is going. */
export function Chips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <p className="chips">
      <span className="cap">{label}</span>
      {items.map((item, i) => <span key={i} className="chip">{item}</span>)}
    </p>
  )
}
