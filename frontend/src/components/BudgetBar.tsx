import { money } from '../format'
import { CATEGORIES, type BudgetSummary, type Traveler } from '../types'

function Row({ name, budget }: { name: string; budget: BudgetSummary }) {
  const over = budget.remaining_usd < 0
  // The track is as wide as whichever is larger, so overspending pushes past the budget marker.
  const scale = Math.max(budget.total_usd, budget.spent_usd) || 1

  return (
    <div className={over ? 'budget-row over' : 'budget-row'}>
      <span className="name">{name}</span>
      <span>
        <strong>{money(budget.spent_usd)}</strong> of {money(budget.total_usd)}
      </span>
      <div className="track">
        {CATEGORIES.map((category) => {
          const spent = budget.by_category[category] ?? 0
          return (
            <div
              key={category}
              className={`seg cat-${category}`}
              style={{ width: `${(spent / scale) * 100}%` }}
              title={`${category}: ${money(spent)} of ${money(budget.allotted[category] ?? 0)} allotted`}
            />
          )
        })}
        {over && <div className="limit" style={{ left: `${(budget.total_usd / scale) * 100}%` }} />}
      </div>
      <span className="remaining">
        {over ? `Over budget by ${money(-budget.remaining_usd)}` : `${money(budget.remaining_usd)} remaining`}
      </span>
    </div>
  )
}

/** One row per traveler: each has their own budget. */
export function BudgetBar({ travelers, budgets }: { travelers: Traveler[]; budgets: Record<string, BudgetSummary> }) {
  const rows = travelers.filter((t) => budgets[t.id])
  if (rows.length === 0) return null
  const over = rows.some((t) => budgets[t.id].remaining_usd < 0)

  return (
    <section className={over ? 'budget over' : 'budget'} aria-label="Budget">
      {rows.map((t) => (
        <Row key={t.id} name={travelers.length > 1 ? t.name : 'Budget'} budget={budgets[t.id]} />
      ))}
    </section>
  )
}
