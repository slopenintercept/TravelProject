import { count, dateRange } from '../format'
import { planningStarted, type TravelerIn, type TripState } from '../types'
import { DraftPlan } from './DraftPlan'
import { EmptyPlan } from './Route'
import { TravelerForm } from './TravelerForm'

/** The trip so far, for someone who is not on it yet: the draft of the days, or where they will appear. */
function TripSoFar({ state }: { state: TripState }) {
  return (
    <aside className="board">
      {state.draft ? <DraftPlan state={state} untagged /> : <EmptyPlan route={state.route} days={state.request.days} />}
    </aside>
  )
}

/** A trip link without a traveler in it: pick who you are, or join. Each person then has their own view. */
export function WhoAreYou({ state }: { state: TripState }) {
  const started = planningStarted(state.stage)
  return (
    <>
      <main className="feed">
        <div className="hd top"><h1 className="display h-40">Who are you?</h1></div>
        <p className="say">Each traveler on the trip to {state.request.destination} reviews their own flight, stays and budget.</p>
        <div className="crew">
          {state.travelers.map((t) => (
            <a key={t.id} className="pill" href={`#${state.id}/${t.id}`}>{t.name}{t.host && ' (host)'}</a>
          ))}
        </div>
        {!started && <p className="lede">Not on the list? <a href={`#${state.id}/join`}>Join the trip</a></p>}
      </main>
      <TripSoFar state={state} />
    </>
  )
}

interface Props {
  state: TripState
  busy: boolean
  onJoin: (traveler: TravelerIn) => Promise<boolean>
}

/** Where the invite link lands: an invited traveler adds themselves and their preferences. */
export function Join({ state, busy, onJoin }: Props) {
  const { request, dates, travelers } = state
  const started = planningStarted(state.stage)

  return (
    <>
      <main className="feed">
        <div className="hd top"><h1 className="display h-40">Join the trip to {request.destination}</h1></div>
        <p className="lede">
          {count(request.days, 'day')}
          {dates && ` · ${dateRange(dates.start, dates.end)}`}
          {travelers.length > 0 && ` · already in: ${travelers.map((t) => t.name).join(', ')}`}
        </p>

        {started ? (
          <p className="say">Planning has already started. <a href={`#${state.id}`}>View the trip</a></p>
        ) : (
          <TravelerForm busy={busy} onSubmit={onJoin} />
        )}
      </main>
      <TripSoFar state={state} />
    </>
  )
}
