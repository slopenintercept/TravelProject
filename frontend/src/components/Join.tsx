import { dateRange } from '../format'
import { planningStarted, type TravelerIn, type TripState } from '../types'
import { TravelerForm } from './TravelerForm'

interface Props {
  state: TripState
  busy: boolean
  onJoin: (traveler: TravelerIn) => Promise<boolean>
}

/** A trip link without a traveler in it: pick who you are, or join. Each person then has their own view. */
export function WhoAreYou({ state }: { state: TripState }) {
  const started = planningStarted(state.stage)
  return (
    <section className="trip-form panel">
      <h1>Who are you?</h1>
      <p className="lede">Each traveler on the trip to {state.request.destination} reviews their own flight, stays and budget.</p>
      <ul className="travelers">
        {state.travelers.map((t) => (
          <li key={t.id}>
            <a className="button" href={`#${state.id}/${t.id}`}>{t.name}{t.host && ' (host)'}</a>
          </li>
        ))}
      </ul>
      {!started && <p className="lede">Not on the list? <a href={`#${state.id}/join`}>Join the trip</a></p>}
    </section>
  )
}

/** Where the invite link lands: an invited traveler adds themselves and their preferences. */
export function Join({ state, busy, onJoin }: Props) {
  const { request, dates, travelers } = state
  const started = planningStarted(state.stage)

  return (
    <section className="trip-form panel">
      <h1>Join the trip to {request.destination}</h1>
      <p className="lede">
        {request.days} days
        {dates && ` · ${dateRange(dates.start, dates.end)}`}
        {travelers.length > 0 && ` · already in: ${travelers.map((t) => t.name).join(', ')}`}
      </p>

      {started ? (
        <>
          <h2>Planning has already started</h2>
          <p className="lede"><a href={`#${state.id}`}>View the trip</a></p>
        </>
      ) : (
        <TravelerForm busy={busy} onSubmit={onJoin} />
      )}
    </section>
  )
}
