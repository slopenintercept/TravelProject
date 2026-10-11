import { Fragment } from 'react'
import { count } from '../format'
import type { RoutePlan } from '../types'

/** The cities in order, with the nights in each. */
export function Route({ route }: { route: RoutePlan }) {
  return (
    <p className="route">
      {route.segments.map((segment, i) => (
        <Fragment key={i}>
          {i > 0 && <span aria-hidden="true">→</span>}
          <span className="chip"><b>{segment.city}</b>{count(segment.nights, 'night')}</span>
        </Fragment>
      ))}
    </p>
  )
}

/** The board before there is a plan: where the route and the days will appear. */
export function EmptyPlan({ route, days }: { route?: RoutePlan | null; days: number }) {
  // A week of placeholders at most: longer trips still read as "your days go here".
  const shown = Math.min(Math.max(days || 7, 1), 7)
  return (
    <div className="empty">
      <div className="hd"><h2>Your route</h2></div>
      {route ? <Route route={route} /> : <div className="ph">Your route appears here once the Route agent proposes it.</div>}
      <div>
        <div className="hd"><h2>Your days</h2></div>
        <div className="ghost-days">
          {Array.from({ length: shown }, (_, i) => <div key={i} className="ph">Day {i + 1}</div>)}
        </div>
      </div>
    </div>
  )
}
