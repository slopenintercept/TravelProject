import { useState } from 'react'
import { clock, monthDay, money } from '../format'
import type { FlightOption, Traveler, TripState } from '../types'

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
    <section className="choose">
      <h1>Choose your flight and stays</h1>
      <p className="lede">
        {planned
          ? "The group's days are already planned; they'll adjust to your choices when you confirm."
          : 'The agents found these for you. Your days are planned around the flight and rooms you confirm.'}
      </p>

      <section className="choose-group">
        <h2>Your flight</h2>
        {!flights || flights.options.length === 0 ? (
          <p className="muted">
            The flight agent didn't find options for you, so your flight shows as pending on the review page. You can
            still confirm your stays.
          </p>
        ) : (
          <ul className="options">
            {flights.options.map((o) => (
              <li key={o.id}>
                <label className={`option panel${o.id === flightId ? ' chosen' : ''}`}>
                  <input type="radio" name="flight" checked={o.id === flightId} onChange={() => setFlightId(o.id)} />
                  <div className="what">
                    <strong>{o.airline}</strong>
                    {o.id === flights.selected_id && <span className="pill">agent's pick</span>}
                    <p>
                      {o.origin} {when(o.depart_at)} → {o.destination} {when(o.arrive_at)} · {hours(o.duration_minutes)} · {stops(o)}
                    </p>
                    {o.return_depart_at && <p className="muted">Flight home leaves {when(o.return_depart_at)}</p>}
                    {o.tradeoff && <p className="reasoning">{o.tradeoff}</p>}
                  </div>
                  <span className="price">{money(o.price_usd)}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>

      {stays.map((stay, i) => (
        <section key={`${stay.city}-${stay.check_in}`} className="choose-group">
          <h2>{stay.city}: {monthDay(stay.check_in)} – {monthDay(stay.check_out)}</h2>
          {stay.reasoning && <p className="muted">{stay.reasoning}</p>}
          <ul className="options">
            {stay.options.map((o) => (
              <li key={o.id}>
                <label className={`option panel${o.id === roomIds[i] ? ' chosen' : ''}`}>
                  <input
                    type="radio"
                    name={`stay-${i}`}
                    checked={o.id === roomIds[i]}
                    onChange={() => setRoomIds(roomIds.map((id, j) => (j === i ? o.id : id)))}
                  />
                  <div className="what">
                    <strong>{o.name}</strong>
                    {o.id === stay.selected_id && <span className="pill">matched to your budget</span>}
                    <p>
                      {o.kind === 'airbnb' ? 'Airbnb' : 'Hotel'}{o.neighborhood && ` · ${o.neighborhood}`}
                      {o.rating !== null && ` · rated ${o.rating}`}
                    </p>
                    {o.location_note && <p className="muted">{o.location_note}</p>}
                  </div>
                  <span className="price">{money(o.price_total_usd)}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <footer className="choose-total panel">
        <div>
          Flight + stays: <strong>{money(total)}</strong> of your {money(you.budget_usd)} budget
          <span className={left < 0 ? 'over' : 'muted'}>
            {left < 0 ? `, ${money(-left)} over before activities.` : `, leaving ${money(left)} for activities and getting around.`}
          </span>
        </div>
        <button className="primary big" disabled={sending} onClick={() => onConfirm(flightId, roomIds)}>
          Confirm my flight and stays
        </button>
      </footer>
    </section>
  )
}
