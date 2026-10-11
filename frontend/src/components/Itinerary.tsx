import { useState } from 'react'
import { clock, daysBetween, money, monthDay, temp, weekday } from '../format'
import type { ItineraryItem, TripState } from '../types'

interface Props {
  state: TripState
  busy: boolean
  onMove: (itemId: string, day: string) => void
  onSwap: (itemId: string, attractionId: string) => void
  onRemove: (attractionId: string) => void
}

export function Itinerary({ state, busy, onMove, onSwap, onRemove }: Props) {
  const [dragId, setDragId] = useState<string | null>(null)
  const [overDay, setOverDay] = useState<string | null>(null)
  const [viewer, setViewer] = useState('') // a traveler id, or '' for everyone

  const { travelers } = state
  const solo = travelers.length < 2
  const names = (ids: string[]) => travelers.filter((t) => ids.includes(t.id)).map((t) => t.name).join(', ')
  // Fewer than everyone at an attraction: some travelers split off for it and regroup afterwards.
  const isSplit = (item: ItineraryItem) => item.kind === 'attraction' && item.travelers.length < travelers.length

  const items = [...state.itinerary].sort((a, b) => (a.day + a.start).localeCompare(b.day + b.start))
  const days = items.length > 0 ? daysBetween(items[0].day, items[items.length - 1].day) : []
  // One traveler's view: what they attend, plus the fixed items (flights and intercity travel).
  const shown = viewer ? items.filter((item) => item.locked || item.travelers.includes(viewer)) : items

  // Attractions that are not on the calendar: removed in review, or the scheduler could not place them.
  const missed = new Set(state.unscheduled.map((u) => u.attraction_id))
  const spare = state.attractions.filter((a) => !a.included || missed.has(a.id))
  // Same rule as the review cards: an attraction someone needs can't be removed.
  const needed = new Set(state.attractions.filter((a) => a.must_have).map((a) => a.id))

  const problems = new Map<string, string[]>()
  for (const violation of state.violations) {
    for (const id of violation.item_ids) problems.set(id, [...(problems.get(id) ?? []), violation.message])
  }

  function endDrag() {
    setDragId(null)
    setOverDay(null)
  }

  function drop(day: string) {
    const item = items.find((i) => i.id === dragId)
    endDrag()
    if (item && item.day !== day) onMove(item.id, day)
  }

  return (
    <div className="itinerary">
      {state.plan_note && <p className="plan-note">{state.plan_note}</p>}
      {!solo && (
        <div className="viewer" role="radiogroup" aria-label="View">
          <strong>View</strong>
          <div className="segmented">
            {[{ id: '', name: 'Everyone' }, ...travelers].map((t) => (
              <label key={t.id}>
                <input type="radio" name="viewer" checked={viewer === t.id} onChange={() => setViewer(t.id)} />
                <span>{t.name}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {days.length === 0 ? (
        <p className="muted">No itinerary yet. It needs dates, a flight and a place to stay.</p>
      ) : (
        <div className="calendar">
          {days.map((day) => {
            const dayItems = shown.filter((item) => item.day === day)
            const weather = state.weather.find((w) => w.day === day)
            const city = [...new Set(dayItems.map((item) => item.city).filter(Boolean))].join(' → ') || weather?.city
            return (
              <section
                key={day}
                className={overDay === day ? 'day over' : 'day'}
                onDragOver={(e) => {
                  if (!dragId) return
                  e.preventDefault() // allows the drop
                  setOverDay(day)
                }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOverDay(null)
                }}
                onDrop={(e) => {
                  e.preventDefault()
                  drop(day)
                }}
              >
                <header>
                  <h3>{weekday(day)} <span>{monthDay(day)}</span></h3>
                  {city && <div className="city">{city}</div>}
                  {weather && (
                    <div className="weather" title={`${weather.summary} (${weather.kind})`}>
                      {weather.high_c !== null && weather.low_c !== null
                        ? `${temp(weather.high_c)} / ${temp(weather.low_c)}`
                        : weather.summary}
                      {weather.precip_prob !== null && ` · ${Math.round(weather.precip_prob)}% rain`}
                    </div>
                  )}
                </header>

                {dayItems.length === 0 && <p className="free">Nothing planned</p>}
                {dayItems.map((item) => (
                  <article
                    key={item.id}
                    className={[
                      'item',
                      item.locked && 'locked',
                      isSplit(item) && 'split',
                      problems.has(item.id) && 'conflict',
                      dragId === item.id && 'dragging',
                    ].filter(Boolean).join(' ')}
                    title={problems.get(item.id)?.join('\n')}
                    draggable={!item.locked && !busy}
                    onDragStart={(e) => {
                      e.dataTransfer.setData('text/plain', item.id) // Firefox needs data to start a drag
                      e.dataTransfer.effectAllowed = 'move'
                      setDragId(item.id)
                    }}
                    onDragEnd={endDrag}
                  >
                    <div className="time">{clock(item.start)} – {clock(item.end)}</div>
                    <div className="title">{item.title}</div>
                    {isSplit(item) && <div className="going">Split-off: {names(item.travelers)}</div>}
                    {item.cost_usd > 0 && <div className="cost">{money(item.cost_usd)}</div>}
                    {item.locked ? (
                      <span className="fixed">fixed</span>
                    ) : (
                      <>
                        {spare.length > 0 && (
                          <select
                            aria-label={`Swap ${item.title} for another attraction`}
                            value=""
                            disabled={busy}
                            onChange={(e) => onSwap(item.id, e.target.value)}
                          >
                            <option value="" disabled>swap…</option>
                            {spare.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.city})</option>)}
                          </select>
                        )}
                        {item.ref_id && !needed.has(item.ref_id) && (
                          <button
                            aria-label={`Remove ${item.title} from the itinerary`}
                            disabled={busy}
                            onClick={() => onRemove(item.ref_id!)}
                          >
                            Remove
                          </button>
                        )}
                      </>
                    )}
                  </article>
                ))}
              </section>
            )
          })}
        </div>
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
