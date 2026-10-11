import { useState } from 'react'
import { capitalize, count, dateRange, money, temp, tomorrow } from '../format'
import type { DateWindow, TripState } from '../types'
import { AgentTag } from './Agents'
import { Board } from './Board'
import { EmptyPlan } from './Route'
import { Crew } from './Working'

interface Props {
  state: TripState
  /** Only the host picks the dates; everyone else sees the options. */
  canChoose: boolean
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

/** Choosing dates: one card per window the agents compared, or the host's own start date. */
export function Timeframe({ state, canChoose, busy, onChoose }: Props) {
  const [custom, setCustom] = useState(state.request.start_date ?? '')
  const { windows, request } = state
  const ready = state.stage === 'awaiting_dates'
  const host = state.travelers.find((t) => t.host)?.name ?? 'The host'

  return (
    <>
      <main className="feed">
        <div className="hd top">
          <h1 className="display h-40">{ready ? 'When do you want to go?' : 'Finding the best time to go'}</h1>
          <AgentTag agent="timeframe" />
        </div>
        <p className="say">
          {!ready
            ? `Agents are researching weather, crowds and fares for ${count(request.days, 'day')} in ${request.destination}.`
            : !canChoose
              ? `${host} is choosing the dates from these options.`
              : windows.length > 0
                ? 'The agents compared weather, crowds and fares. Choose a window, or pick your own start date.'
                : 'The agents had no data to suggest dates for this trip. Pick your own start date to keep going.'}
        </p>
        {!ready && <Crew />}

        {windows.map((w) => (
          <article key={w.id} className="card choice">
            <div className="top">
              <div>
                <span className="cap">{capitalize(w.crowd_level)} crowds</span>
                <h3>{dateRange(w.start, w.end)}</h3>
              </div>
              <div className="price" title="Cheapest fare found">{w.cheapest_fare_usd !== null ? money(w.cheapest_fare_usd) : ''}</div>
            </div>
            <div className="facts">
              <span className="chip wrap">{weather(w) || 'No weather data'}</span>
              {w.cheapest_fare_usd === null && <span className="chip">No fare found</span>}
            </div>
            {w.reasoning && <p className="why"><b>Why these dates.</b> {w.reasoning}</p>}
            {(w.price_trend || w.notes) && <p className="why">{[w.price_trend, w.notes].filter(Boolean).join(' ')}</p>}
            {canChoose && (
              <div className="go flush">
                <button className="pill sm solid" disabled={!ready || busy} onClick={() => onChoose(w.start)}>Choose these dates</button>
              </div>
            )}
          </article>
        ))}

        {ready && canChoose && (
          <form
            className="own-date"
            onSubmit={(e) => {
              e.preventDefault()
              onChoose(custom)
            }}
          >
            <div className="card ticket">
              <label className="row">
                <span>{windows.length > 0 ? 'Or pick your own start date' : 'Start date'}</span>
                <input className="field" type="date" required min={tomorrow()} value={custom} onChange={(e) => setCustom(e.target.value)} />
              </label>
            </div>
            <div className="go"><button className="pill" disabled={busy}>Use this date</button></div>
          </form>
        )}
      </main>

      <Board plan="Your route" detailed={!ready}>
        <EmptyPlan route={state.route} days={request.days} />
      </Board>
    </>
  )
}
