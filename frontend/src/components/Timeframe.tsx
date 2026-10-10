import { useState } from 'react'
import { dateRange, money, temp, tomorrow } from '../format'
import type { DateWindow, TripState } from '../types'

interface Props {
  state: TripState
  busy: boolean
  onChoose: (start: string) => void
}

function weather(w: DateWindow): string {
  if (w.weather_summary) return w.weather_summary
  const parts = []
  if (w.avg_high_c !== null) parts.push(`highs around ${temp(w.avg_high_c)}`)
  if (w.avg_low_c !== null) parts.push(`lows around ${temp(w.avg_low_c)}`)
  if (w.rainy_days !== null) parts.push(`${w.rainy_days} rainy day${w.rainy_days === 1 ? '' : 's'}`)
  return parts.join(' · ')
}

export function Timeframe({ state, busy, onChoose }: Props) {
  const [custom, setCustom] = useState(state.request.start_date ?? '')
  const { windows, request } = state
  const ready = state.stage === 'awaiting_dates'

  return (
    <section className="timeframe">
      <h1>{ready ? 'When do you want to go?' : 'Finding the best time to go'}</h1>
      <p className="lede">
        {!ready
          ? `Agents are researching weather, crowds and fares for ${request.days} days in ${request.destination}.`
          : windows.length > 0
            ? 'The agents compared weather, crowds and fares. Choose a window, or pick your own start date.'
            : 'The agents had no data to suggest dates for this trip. Pick your own start date to keep going.'}
      </p>

      {windows.length > 0 && (
        <div className="windows">
          {windows.map((w) => (
            <article key={w.id} className="panel window">
              <h2>{dateRange(w.start, w.end)}</h2>
              <dl>
                <dt>Weather</dt>
                <dd>{weather(w) || 'No weather data'}</dd>
                <dt>Crowds</dt>
                <dd><span className={`pill crowd-${w.crowd_level}`}>{w.crowd_level}</span></dd>
                <dt>Cheapest fare</dt>
                <dd>
                  <strong>{w.cheapest_fare_usd !== null ? money(w.cheapest_fare_usd) : 'Not found'}</strong>
                  {w.price_trend && <span className="muted"> · {w.price_trend}</span>}
                </dd>
                {w.notes && (
                  <>
                    <dt>Notes</dt>
                    <dd>{w.notes}</dd>
                  </>
                )}
              </dl>
              {w.reasoning && <p className="reasoning">{w.reasoning}</p>}
              <button className="primary" disabled={!ready || busy} onClick={() => onChoose(w.start)}>
                Choose these dates
              </button>
            </article>
          ))}
        </div>
      )}

      {ready && (
        <form
          className="custom-date"
          onSubmit={(e) => {
            e.preventDefault()
            onChoose(custom)
          }}
        >
          <label htmlFor="custom-start">{windows.length > 0 ? 'or pick your own start date' : 'Start date'}</label>
          <input id="custom-start" type="date" required min={tomorrow()} value={custom} onChange={(e) => setCustom(e.target.value)} />
          <button disabled={busy}>Use this date</button>
        </form>
      )}
    </section>
  )
}
