import { useState } from 'react'
import { clock, money, monthDay, temp, weekday } from '../format'
import type { Traveler, TripState } from '../types'
import { CalendarGrid } from './CalendarGrid'

interface Props {
  state: TripState
  you: Traveler
  busy: boolean
  onMove: (itemId: string, day: string) => void
  onSwap: (itemId: string, attractionId: string) => void
  onRemove: (attractionId: string) => void
}

/** The trip's days on a week-view calendar: drag an activity to another day, or click it to swap or remove it. */
export function Itinerary({ state, you, busy, onMove, onSwap, onRemove }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { travelers } = state
  const solo = travelers.length < 2
  const names = (ids: string[]) =>
    ids.length === travelers.length ? 'Everyone' : travelers.filter((t) => ids.includes(t.id)).map((t) => t.name).join(', ')

  // Attractions that are not on the calendar: removed in review, or the scheduler could not place them.
  const missed = new Set(state.unscheduled.map((u) => u.attraction_id))
  const spare = state.attractions.filter((a) => !a.included || missed.has(a.id))
  // Same rule as the review cards: an attraction someone needs can't be removed.
  const needed = new Set(state.attractions.filter((a) => a.must_have).map((a) => a.id))

  const problems = new Map<string, string[]>()
  for (const violation of state.violations) {
    for (const id of violation.item_ids) problems.set(id, [...(problems.get(id) ?? []), violation.message])
  }

  function weather(day: string) {
    const w = state.weather.find((x) => x.day === day)
    if (!w) return undefined
    const range = w.high_c !== null && w.low_c !== null ? `${temp(w.high_c)} / ${temp(w.low_c)}` : w.summary
    return w.precip_prob !== null ? `${range} · ${Math.round(w.precip_prob)}% rain` : range
  }

  // The selection can disappear after a re-plan (a move or swap makes new items).
  const selected = state.itinerary.find((i) => i.id === selectedId && !i.locked)

  return (
    <div className="itinerary">
      {state.plan_note && <p className="plan-note">{state.plan_note}</p>}
      {state.itinerary.length === 0 ? (
        <p className="muted">No itinerary yet. It needs dates, a flight and a place to stay.</p>
      ) : (
        <>
          <p className="muted hint">Drag an activity to another day to move it there. Click one to swap it or take it off.</p>
          <CalendarGrid
            items={state.itinerary}
            travelers={travelers}
            you={you}
            busy={busy}
            onMove={(itemId, day) => {
              setSelectedId(null)
              onMove(itemId, day)
            }}
            onSelect={(item) => setSelectedId(item.id === selectedId ? null : item.id)}
            selectedId={selected?.id}
            problems={problems}
            dayNote={weather}
          />
        </>
      )}

      {selected && (
        <section className="selected-item panel">
          <header>
            <h3>{selected.title}</h3>
            <button className="link" onClick={() => setSelectedId(null)}>Close</button>
          </header>
          <p className="muted">
            {weekday(selected.day)} {monthDay(selected.day)} · {clock(selected.start)}–{clock(selected.end)} · {selected.city}
            {!solo && ` · ${names(selected.travelers)}`}
            {selected.cost_usd > 0 && ` · ${money(selected.cost_usd)}`}
          </p>
          {problems.get(selected.id)?.map((message) => <p key={message} className="flag flag-pending">{message}</p>)}
          <footer>
            {spare.length > 0 && (
              <select
                aria-label={`Swap ${selected.title} for another attraction`}
                value=""
                disabled={busy}
                onChange={(e) => {
                  setSelectedId(null)
                  onSwap(selected.id, e.target.value)
                }}
              >
                <option value="" disabled>Swap for…</option>
                {spare.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.city})</option>)}
              </select>
            )}
            {selected.ref_id && !needed.has(selected.ref_id) && (
              <button
                disabled={busy}
                onClick={() => {
                  setSelectedId(null)
                  onRemove(selected.ref_id!)
                }}
              >
                Take it off the trip
              </button>
            )}
            {selected.ref_id && needed.has(selected.ref_id) && <span className="muted">Someone needs this, so it stays.</span>}
          </footer>
        </section>
      )}

      {state.unscheduled.length > 0 && (
        <section className="unscheduled panel">
          <h3>Not on the calendar</h3>
          <ul>
            {state.unscheduled.map((u) => (
              <li key={u.attraction_id}>
                <strong>{u.name}:</strong> {u.reason}
                {!solo && u.wanted_by.length > 0 && <span className="muted"> · wanted by {names(u.wanted_by)}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
