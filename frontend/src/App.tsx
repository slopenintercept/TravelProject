import { useEffect, useState } from 'react'
import { api } from './api'
import { AgentPanel } from './components/AgentPanel'
import { BudgetBar } from './components/BudgetBar'
import { Finish } from './components/Finish'
import { Gathering } from './components/Gathering'
import { Itinerary } from './components/Itinerary'
import { Join } from './components/Join'
import { Review, Violations } from './components/Review'
import { Timeframe } from './components/Timeframe'
import { TripForm } from './components/TripForm'
import { monthDay } from './format'
import { useTrip } from './useTrip'

/** The trip id lives in the URL hash, so a reload resumes the trip. The hash is `#<tripId>`,
 *  or `#<tripId>/join` for the invite link. */
function routeFromHash() {
  const [tripId, page] = window.location.hash.slice(1).split('/')
  return { tripId: tripId || null, joining: page === 'join' }
}

export default function App() {
  const [{ tripId, joining }, setRoute] = useState(routeFromHash)
  const [tab, setTab] = useState<'review' | 'itinerary'>('review')
  const [finishing, setFinishing] = useState(false)
  const { view, lanes, busy, error, notice, act, setError, setNotice } = useTrip(tripId)

  useEffect(() => {
    const onHashChange = () => {
      setRoute(routeFromHash())
      setFinishing(false)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const state = view?.state
  const stage = state?.stage
  const group = state?.travelers.length ?? 0
  // The first response of a stage can arrive before the server marks the trip busy.
  const working = busy || stage === 'created' || stage === 'timeframe' || stage === 'planning'

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#">Tripwright</a>
        {state && (
          <span className="trip">
            {group < 2 && `${state.request.origin} → `}{state.request.destination} · {state.request.days} days
            {state.dates && ` · ${monthDay(state.dates.start)} – ${monthDay(state.dates.end)}`}
            {group > 1 && ` · ${group} travelers`}
          </span>
        )}
        {state && working && <span className="working"><i className="spinner" />Agents working…</span>}
        {tripId && <a className="new-trip" href="#">New trip</a>}
      </header>

      {state && <BudgetBar travelers={state.travelers} budgets={state.budgets} />}

      <main>
        {error && (
          <div className="banner error" role="alert">
            <span>{error}</span>
            <button className="link" onClick={() => setError('')}>Dismiss</button>
          </div>
        )}
        {notice && (
          <div className="banner warn" role="status">
            <span>{notice}</span>
            <button className="link" onClick={() => setNotice('')}>Dismiss</button>
          </div>
        )}

        {!tripId ? (
          <TripForm onCreated={(id) => { window.location.hash = id }} />
        ) : !view || !state ? (
          !error && <p className="lede">Loading your trip…</p>
        ) : joining ? (
          <Join
            state={state}
            busy={busy}
            onJoin={async (traveler) => {
              const joined = await act(api.join(state.id, traveler))
              if (joined) window.location.hash = state.id
              return joined
            }}
          />
        ) : stage === 'review' && finishing ? (
          <Finish view={view} onBack={() => setFinishing(false)} />
        ) : stage === 'review' ? (
          <>
            <AgentPanel lanes={lanes} travelers={state.travelers} compact />
            <nav className="tabs" role="tablist">
              <button role="tab" aria-selected={tab === 'review'} onClick={() => setTab('review')}>Review</button>
              <button role="tab" aria-selected={tab === 'itinerary'} onClick={() => setTab('itinerary')}>Itinerary</button>
            </nav>
            <Violations violations={state.violations} />
            {tab === 'review' ? (
              <Review
                view={view}
                busy={busy}
                onDecision={(action, card, optionId) => act(api.decide(state.id, action, card, optionId))}
                onApplyBudget={(travelerId) => act(api.applyBudget(state.id, travelerId))}
              />
            ) : (
              <Itinerary
                state={state}
                busy={busy}
                onMove={(itemId, day) => act(api.moveItem(state.id, itemId, day))}
                onSwap={(itemId, attractionId) => act(api.swapItem(state.id, itemId, attractionId))}
                onRemove={(attractionId) => act(api.decide(state.id, 'remove', `attraction:${attractionId}`))}
              />
            )}
            <button className="primary big finish-button" disabled={busy} onClick={() => { setFinishing(true); window.scrollTo(0, 0) }}>
              Finish →
            </button>
          </>
        ) : stage === 'planning' ? (
          <>
            <h1>Planning your trip</h1>
            <p className="lede">
              Each specialist researches on its own. The orchestrator checks every result and sends back what does not hold up.
            </p>
            <AgentPanel lanes={lanes} travelers={state.travelers} />
          </>
        ) : stage === 'gathering' ? (
          <Gathering
            state={state}
            busy={busy}
            onAdd={(traveler) => act(api.join(state.id, traveler))}
            onRemove={(travelerId) => act(api.leave(state.id, travelerId))}
            onPlan={() => act(api.plan(state.id))}
          />
        ) : (
          <>
            <Timeframe state={state} busy={busy} onChoose={(start) => act(api.chooseDates(state.id, start))} />
            <AgentPanel lanes={lanes} travelers={state.travelers} />
          </>
        )}
      </main>
    </>
  )
}
