import { useState } from 'react'
import { clock, count, monthDay, money } from '../format'
import type { FlightOption, Traveler, TripState } from '../types'
import { AgentTag } from './Agents'
import { Board } from './Board'
import { Days } from './Days'
import { DraftPlan } from './DraftPlan'

/** "2027-01-18T08:50:00" -> "Jan 18 08:50" */
const when = (datetime: string) => `${monthDay(datetime.slice(0, 10))} ${clock(datetime.slice(11))}`
const hours = (minutes: number) => `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`

function stops(o: FlightOption) {
  if (o.stops === 0) return 'nonstop'
  return `${o.stops} stop${o.stops > 1 ? 's' : ''}${o.layovers.length ? ` (${o.layovers.join(', ')})` : ''}`
}

interface Props {
  state: TripState
  you: Traveler
  /** Your own confirm is on its way (the trip itself may be busy researching for minutes). */
  sending: boolean
  onConfirm: (flightId: string | null, stayIds: string[]) => void
}

/** Each traveler chooses their own flight and a room for each stay before the days are planned around them. */
export function Choose({ state, you, sending, onConfirm }: Props) {
  const flights = you.flights
  const stays = you.lodging?.stays ?? []
  const [flightId, setFlightId] = useState(flights?.selected_id ?? null)
  const [roomIds, setRoomIds] = useState(stays.map((s) => s.selected_id))

  const flight = flights?.options.find((o) => o.id === flightId)
  const rooms = stays.map((s, i) => s.options.find((o) => o.id === roomIds[i]))
  const total = (flight?.price_usd ?? 0) + rooms.reduce((sum, r) => sum + (r?.price_total_usd ?? 0), 0)
  const left = you.budget_usd - total
  const planned = state.stage === 'review'

  return (
    <>
      <main className="feed">
        <div className="hd top"><h1 className="display h-40">Choose your flight and stays</h1></div>
        <p className="say">
          {planned
            ? "The group's days are already planned; they'll adjust to your choices when you confirm."
            : 'The agents found these for you. Your days are planned around the flight and rooms you confirm.'}
        </p>

        <section>
          <div className="hd"><h2>Your flight</h2><AgentTag agent={`flight:${you.id}`} /></div>
          {!flights || flights.options.length === 0 ? (
            <p className="small">
              The flight agent didn't find options for you, so your flight shows as pending at review. You can still
              confirm your stays.
            </p>
          ) : flights.options.map((o) => (
            <label key={o.id} className="opt">
              <input type="radio" name="flight" checked={o.id === flightId} onChange={() => setFlightId(o.id)} />
              <div className="what">
                <b>{o.airline}{o.id === flights.selected_id && <small>Agent's pick</small>}</b>
                <p>{o.origin} {when(o.depart_at)} → {o.destination} {when(o.arrive_at)} · {hours(o.duration_minutes)} · {stops(o)}</p>
                {o.return_depart_at && <p>Flight home leaves {when(o.return_depart_at)}</p>}
                {o.tradeoff && <p>{o.tradeoff}</p>}
              </div>
              <span className="n">{money(o.price_usd)}</span>
            </label>
          ))}
        </section>

        {stays.map((stay, i) => (
          <section key={`${stay.city}-${stay.check_in}`}>
            <div className="hd"><h2>Your stay in {stay.city}</h2><AgentTag agent="lodging" words={count(stay.options.length, 'option')} /></div>
            <p className="small">{monthDay(stay.check_in)} – {monthDay(stay.check_out)}{stay.reasoning && ` · ${stay.reasoning}`}</p>
            {stay.options.map((o) => (
              <label key={o.id} className="opt">
                <input
                  type="radio"
                  name={`stay-${i}`}
                  checked={o.id === roomIds[i]}
                  onChange={() => setRoomIds(roomIds.map((id, j) => (j === i ? o.id : id)))}
                />
                <div className="what">
                  <b>{o.name}{o.id === stay.selected_id && <small>Matched to your budget</small>}</b>
                  <p>
                    {o.kind === 'airbnb' ? 'Airbnb' : 'Hotel'}{o.neighborhood && ` · ${o.neighborhood}`}
                    {o.rating !== null && ` · rated ${o.rating}`}
                  </p>
                  {o.location_note && <p>{o.location_note}</p>}
                </div>
                <span className="n">{money(o.price_total_usd)}</span>
              </label>
            ))}
          </section>
        ))}

        <footer className="card total">
          <p>
            Flight and stays: <b>{money(total)}</b> of your {money(you.budget_usd)} budget
            <span className={left < 0 ? 'bad' : undefined}>
              {left < 0 ? `, ${money(-left)} over before activities.` : `, leaving ${money(left)} for activities and getting around.`}
            </span>
          </p>
          <button className="pill solid" disabled={sending} onClick={() => onConfirm(flightId, roomIds)}>
            Confirm my flight and stays →
          </button>
        </footer>
      </main>

      {state.itinerary.length > 0 ? (
        <Board plan="Your days"><Days state={state} you={you} /></Board>
      ) : (
        <Board plan="Draft plan"><DraftPlan state={state} musts={you.need} /></Board>
      )}
    </>
  )
}
