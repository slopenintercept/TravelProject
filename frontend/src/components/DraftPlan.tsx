import type { ReactNode } from 'react'
import { daysBetween, weekday, whoIsIn } from '../format'
import { planningStarted, type TripState } from '../types'
import { AgentTag } from './Agents'
import { cityOn } from './Calendar'
import { PlaceMap } from './Map'
import { Route } from './Route'

/** Place names match whatever their capitals and spacing. */
export const placeKey = (name: string) => name.toLowerCase().split(/\s+/).join(' ')

interface Props {
  state: TripState
  /** Names of the places the traveler looking has marked must do: these stand out on the days. */
  musts?: string[]
  /** Leave the agent's tag off, where the board has no Agents tab for it to open. */
  untagged?: boolean
  /** What sits under the days: the tallies and "Save my picks". */
  children?: ReactNode
}

/** The rough sketch of the days from everyone's picks, rebuilt shortly after anyone saves theirs. */
export function DraftPlan({ state, musts = [], untagged, children }: Props) {
  const { draft, travelers } = state
  // The draft is rebuilt only until planning starts; after that its agent's last status is stale.
  const live = !planningStarted(state.stage)
  const status = live ? state.agents.draft : undefined
  const route = draft?.route ?? state.route
  const must = new Set(musts.map(placeKey))
  const pins = state.ideas.flatMap((idea) =>
    idea.lat == null || idea.lon == null ? [] : [{ name: idea.name, lat: idea.lat, lon: idea.lon, filled: must.has(placeKey(idea.name)) }])
  const names = (ids: string[]) => travelers.filter((t) => ids.includes(t.id)).map((t) => t.name)
  const visits = draft?.itinerary.filter((i) => i.kind === 'attraction') ?? []
  const sorted = [...(draft?.itinerary ?? [])].sort((a, b) => (a.day + a.start).localeCompare(b.day + b.start))
  const days = sorted.length ? daysBetween(sorted[0].day, sorted[sorted.length - 1].day) : []

  return (
    <>
      <div className="board-h">
        <h2>Draft plan</h2>
        {!untagged && live && <AgentTag agent="draft" />}
      </div>
      {route && <Route route={route} />}
      <PlaceMap pins={pins} />
      <p className="small">
        {live
          ? "A rough sketch from everyone's picks, rebuilt a few seconds after anyone saves theirs. Times are typical ones; real flights, hotels, hours and prices come when the host starts planning."
          : "The rough sketch from everyone's picks. Your real days replace it once flights and stays are chosen."}
      </p>

      {days.length === 0 ? (
        <div className="draft"><div className="ph" style={{ gridColumn: '1 / -1', height: 170 }}>
          {!live ? 'Your days appear here once flights and stays are chosen.'
            : status?.status === 'failed' ? `Couldn't update the draft: ${status.message}`
            : status && ['working', 'under_review', 'sent_back'].includes(status.status) ? 'Building the first draft…'
            : 'The draft appears once people have marked some places.'}
        </div></div>
      ) : (
        <div className="draft" style={{ gridTemplateColumns: `repeat(${Math.min(days.length, 7)}, minmax(0, 1fr))` }}>
          {days.map((day) => (
            <div key={day} className="dcol">
              <h3>{weekday(day)} {Number(day.slice(8))}<small>{cityOn(day, sorted)}</small></h3>
              <ul>
                {visits.filter((i) => i.day === day).sort((a, b) => a.start.localeCompare(b.start)).map((item) => (
                  <li key={item.id} className={must.has(placeKey(item.title)) ? 'must' : undefined}>
                    {item.title}
                    {item.travelers.length < travelers.length && <small>{names(item.travelers).join(', ')} only</small>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {children}

      {draft?.note && <p className="aside">{draft.note}</p>}
      {draft && draft.unscheduled.length > 0 && (
        <div className="aside">
          <b>Doesn't fit yet</b>
          <ul>
            {draft.unscheduled.map((u) => (
              <li key={u.attraction_id}>
                <b>{u.name}</b>
                {u.wanted_by.length > 0 && ` (${whoIsIn(names(u.wanted_by), travelers.length).join(', ')})`}: {u.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
