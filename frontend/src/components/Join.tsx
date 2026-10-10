import { dateRange } from '../format'
import type { TravelerIn, TripState } from '../types'
import { TravelerForm } from './TravelerForm'

interface Props {
  state: TripState
  busy: boolean
  onJoin: (traveler: TravelerIn) => Promise<boolean>
}

/** Where the invite link lands: an invited traveler adds themselves and their preferences. */
export function Join({ state, busy, onJoin }: Props) {
  const { request, dates, travelers } = state
  const started = state.stage === 'planning' || state.stage === 'review'

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
