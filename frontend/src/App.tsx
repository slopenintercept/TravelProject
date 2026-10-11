import { useEffect, useState } from 'react'
import { actAs, api } from './api'
import { AgentPanel } from './components/AgentPanel'
import { BudgetBar } from './components/BudgetBar'
import { Finish } from './components/Finish'
import { Gathering } from './components/Gathering'
import { Itinerary } from './components/Itinerary'
import { Choose } from './components/Choose'
import { Join, WhoAreYou } from './components/Join'
import { Picks } from './components/Picks'
import { Review, Violations } from './components/Review'
import { Timeframe } from './components/Timeframe'
import { TripForm } from './components/TripForm'
import { monthDay } from './format'
import { planningStarted } from './types'
import { useTrip } from './useTrip'

/** The trip lives in the URL hash, so a reload resumes it. Each traveler has their own link, `#<tripId>/<travelerId>`;
 *  `#<tripId>/join` is the invite link, and a bare `#<tripId>` asks who you are. */
function routeFromHash() {
  const [tripId, page] = window.location.hash.slice(1).split('/')
  return { tripId: tripId || null, joining: page === 'join', me: page && page !== 'join' ? page : null }
}

export default function App() {
  const [{ tripId, joining, me }, setRoute] = useState(routeFromHash)
  const [tab, setTab] = useState<'review' | 'itinerary'>('review')
  const [finishing, setFinishing] = useState(false)
  const [editingPicks, setEditingPicks] = useState(false)
  const { view, lanes, busy, sending, error, notice, act, setError, setNotice } = useTrip(tripId)

  useEffect(() => actAs(me), [me])
  const retry = () => tripId && act(api.retry(tripId))

  useEffect(() => {
    const onHashChange = () => {
      setRoute(routeFromHash())
      setFinishing(false)
      setEditingPicks(false)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const state = view?.state
  const stage = state?.stage
  const group = state?.travelers.length ?? 0
  const you = state?.travelers.find((t) => t.id === me)
  // The first response of a stage can arrive before the server marks the trip busy.
  const working = busy || stage === 'created' || stage === 'timeframe' || stage === 'planning' || stage === 'choosing'
  // Everyone marks the ideas list before planning starts, and can come back to change their marks until then.
  const beforePlanning = !!stage && !planningStarted(stage)
  const picking = !!you && beforePlanning && (!you.picked || editingPicks)
  // Then each traveler chooses their own flight and rooms, once their agents have found the options.
  const choosing = !!you && (stage === 'choosing' || stage === 'review') && !you.confirmed
  const optionsReady = !!you && (stage === 'review' || [`flight:${you.id}`, 'lodging'].every((agent) => {
    const status = state?.agents[agent]?.status
    return !!status && !['idle', 'working', 'under_review', 'sent_back'].includes(status)
  }))

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
        {you && group > 1 && (
          <span className="you">You: <strong>{you.name}</strong> · <a href={`#${tripId}`}>Switch</a></span>
        )}
        {you?.picked && beforePlanning && !editingPicks && (
          <button className="link" onClick={() => setEditingPicks(true)}>Edit my picks</button>
        )}
        {tripId && <a className="new-trip" href="#">New trip</a>}
      </header>

      {state && you && <BudgetBar travelers={[you]} budgets={state.budgets} />}

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
          <TripForm onCreated={(id, hostId) => { window.location.hash = `${id}/${hostId}` }} />
        ) : !view || !state ? (
          !error && <p className="lede">Loading your trip…</p>
        ) : joining ? (
          <Join
            state={state}
            busy={busy}
            onJoin={async (traveler) => {
              const joined = await act(api.join(state.id, traveler))
              if (joined?.you) window.location.hash = `${state.id}/${joined.you}` // their own link from now on
              return !!joined
            }}
          />
        ) : !you ? (
          <WhoAreYou state={state} />
        ) : picking ? (
          <Picks
            state={state}
            you={you}
            busy={busy}
            onSave={async (picks) => {
              const saved = await act(api.savePicks(state.id, you.id, picks))
              if (saved) {
                setEditingPicks(false)
                window.scrollTo(0, 0)
              }
              return !!saved
            }}
            onAdd={async (name, city) => !!(await act(api.addIdea(state.id, name, city)))}
            onMore={async (picks) => !!(await act(api.suggestMore(state.id, picks)))}
          />
        ) : choosing && optionsReady ? (
          <>
            <AgentPanel lanes={lanes} travelers={state.travelers} compact onRetry={retry} busy={busy} />
            <Choose
              state={state}
              you={you}
              sending={sending}
              onConfirm={async (flightId, stayIds) => {
                if (await act(api.confirmChoices(state.id, you.id, flightId, stayIds))) window.scrollTo(0, 0)
              }}
            />
          </>
        ) : choosing || stage === 'choosing' ? (
          <>
            <h1>{choosing ? 'Planning your flight and stays' : 'Planning activities around your choices'}</h1>
            <p className="lede">
              {choosing
                ? "The agents are finding your flight and rooms. You'll choose them here as soon as they're ready."
                : 'The agents are still researching activities, transport and weather. Your days are planned around your flight and rooms as soon as they finish.'}
            </p>
            <AgentPanel lanes={lanes} travelers={state.travelers} onRetry={retry} busy={busy} />
          </>
        ) : stage === 'review' && finishing ? (
          <Finish view={view} you={you} onBack={() => setFinishing(false)} />
        ) : stage === 'review' ? (
          <>
            <AgentPanel lanes={lanes} travelers={state.travelers} compact onRetry={retry} busy={busy} />
            <nav className="tabs" role="tablist">
              <button role="tab" aria-selected={tab === 'review'} onClick={() => setTab('review')}>Review</button>
              <button role="tab" aria-selected={tab === 'itinerary'} onClick={() => setTab('itinerary')}>Itinerary</button>
            </nav>
            <Violations violations={state.violations} />
            {tab === 'review' ? (
              <Review
                view={view}
                you={you}
                busy={busy}
                onDecision={(action, card, optionId) => act(api.decide(state.id, action, card, optionId))}
                onApplyBudget={(travelerId) => act(api.applyBudget(state.id, travelerId))}
              />
            ) : (
              <Itinerary
                state={state}
                you={you}
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
            you={you}
            busy={busy}
            onRemove={async (travelerId) => {
              const left = await act(api.leave(state.id, travelerId))
              if (left && travelerId === you.id) window.location.hash = state.id
            }}
            onPlan={() => act(api.plan(state.id))}
          />
        ) : (
          <>
            <Timeframe
              state={state}
              canChoose={you.host}
              busy={busy}
              onChoose={(start) => act(api.chooseDates(state.id, start))}
            />
            <AgentPanel lanes={lanes} travelers={state.travelers} />
          </>
        )}
      </main>
    </>
  )
}
