import { useState, type ReactNode } from 'react'
import { money } from '../format'
import { CATEGORIES, type BudgetSummary, type ItineraryItem, type Traveler, type TripState } from '../types'
import { AgentTag } from './Agents'
import { Calendar } from './Calendar'

/** One traveler's budget: what the plan costs against it, split by category, with a marker at the budget. */
export function Budget({ budget }: { budget: BudgetSummary }) {
  const over = budget.remaining_usd < 0
  // The bar is as wide as whichever is larger, so overspending pushes past the budget marker.
  const scale = Math.max(budget.total_usd, budget.spent_usd) || 1

  return (
    <section className="budget" aria-label="Budget">
      <div className="fig">{money(budget.spent_usd)} <small>of {money(budget.total_usd)}</small></div>
      <AgentTag agent="budget" />
      <div className="meterbar">
        <div className="segs">
          {CATEGORIES.map((category) => {
            const spent = budget.by_category[category] ?? 0
            return (
              <i
                key={category}
                style={{ width: `${(spent / scale) * 100}%`, background: `var(--c-${category})` }}
                title={`${category}: ${money(spent)} of ${money(budget.allotted[category] ?? 0)} allotted`}
              />
            )
          })}
        </div>
        {over && <span className="limit" style={{ left: `${(budget.total_usd / scale) * 100}%` }} />}
      </div>
      <span className={over ? 'over' : 'over under'}>
        {over ? `Over by ${money(-budget.remaining_usd)}` : `${money(budget.remaining_usd)} left`}
      </span>
    </section>
  )
}

interface Props {
  state: TripState
  you: Traveler
  busy?: boolean
  /** What sits at the end of the headline row: "Finish". */
  action?: ReactNode
  /** Without these the calendar is read-only. */
  onMove?: (itemId: string, day: string) => void
  onSelect?: (item: ItineraryItem) => void
  selectedId?: string | null
}

/** "Your days": the trip on a week calendar, for everyone or one traveler at a time. */
export function Days({ state, you, busy, action, onMove, onSelect, selectedId }: Props) {
  const [viewer, setViewer] = useState('') // a traveler id, or '' for everyone
  const { travelers } = state
  const others = travelers.filter((t) => t.id !== you.id)
  const views = [{ id: '', name: 'Everyone' }, { id: you.id, name: 'Just me' }, ...others]

  const problems = new Map<string, string[]>()
  for (const violation of state.violations) {
    for (const id of violation.item_ids) problems.set(id, [...(problems.get(id) ?? []), violation.message])
  }

  return (
    <>
      <div className="board-h">
        <h2>Your days</h2>
        <AgentTag agent="scheduler" />
        <span className="grow" />
        {others.length > 0 && (
          <div className="view" role="group" aria-label="Whose days to show">
            {views.map((v) => (
              <button key={v.id} aria-pressed={viewer === v.id} onClick={() => setViewer(v.id)}>{v.name}</button>
            ))}
          </div>
        )}
        {action}
      </div>

      {state.itinerary.length === 0 ? (
        <div className="ph">No days yet. They need dates, a flight and a place to stay.</div>
      ) : (
        <Calendar
          items={state.itinerary}
          travelers={travelers}
          you={you}
          viewer={viewer}
          weather={state.weather}
          busy={busy}
          onMove={onMove}
          onSelect={onSelect}
          selectedId={selectedId}
          problems={problems}
        />
      )}

      <div className="note">
        <span>
          {onMove
            ? 'Drag an activity to another day to move it there. Click one to swap it or take it off.'
            : others.length > 0 && state.plan_note}
        </span>
        {others.length > 0 && (
          <span className="key">
            <span><i style={{ background: 'var(--solo-edge)' }} />{others.length > 1 ? 'With you, not everyone' : `${you.name} only`}</span>
            <span><i style={{ background: 'var(--alt)' }} />{others.length > 1 ? 'Without you' : `${others[0].name} only`}</span>
          </span>
        )}
      </div>
      {onMove && others.length > 0 && state.plan_note && <p className="aside">{state.plan_note}</p>}
    </>
  )
}
