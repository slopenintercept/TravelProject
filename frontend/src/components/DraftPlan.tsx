import { clock, whoIsIn } from '../format'
import type { Traveler, TripState } from '../types'
import { CalendarGrid } from './CalendarGrid'

const STILL_WORKING = ['working', 'under_review', 'sent_back']

/** The rough sketch of the days from everyone's picks, rebuilt shortly after anyone saves theirs. */
export function DraftPlan({ state, you }: { state: TripState; you: Traveler }) {
  const { draft, travelers } = state
  const status = state.agents.draft
  const building = !!status && STILL_WORKING.includes(status.status)
  const names = (ids: string[]) => whoIsIn(travelers.filter((t) => ids.includes(t.id)).map((t) => t.name), travelers.length)

  return (
    <section className="draft panel">
      <header>
        <h2>Draft plan</h2>
        <span className="muted">
          {building ? <><i className="spinner" />{status.message || 'Updating…'}</>
            : status?.status === 'failed' ? `Couldn't update the draft: ${status.message}`
              : draft?.built_at ? `Updated ${clock(draft.built_at.slice(11, 19))}` : ''}
        </span>
      </header>
      <p className="muted">
        A rough sketch from everyone's picks, rebuilt a few seconds after anyone saves theirs. Times are typical
        ones; real flights, hotels, hours and prices come when the host starts planning.
        {draft?.route && <> Route: <strong>{draft.route.segments.map((s) => `${s.city} (${s.nights}n)`).join(' → ')}</strong>.</>}
      </p>

      {!draft ? (
        <p className="muted">{building ? 'Building the first draft…' : 'The draft appears once people have marked some places.'}</p>
      ) : (
        <>
          {draft.note && <p className="note">{draft.note}</p>}
          <CalendarGrid items={draft.itinerary} travelers={travelers} you={you} />
          {draft.unscheduled.length > 0 && (
            <div className="unfit">
              <h3>Doesn't fit yet</h3>
              <ul>
                {draft.unscheduled.map((u) => (
                  <li key={u.attraction_id}>
                    <strong>{u.name}</strong> <span className="muted">({names(u.wanted_by).join(', ')}): {u.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}
