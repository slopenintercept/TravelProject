import { Fragment, useEffect, useState } from 'react'
import { actAs, api } from './api'
import { Choose } from './components/Choose'
import { Finish } from './components/Finish'
import { Gathering } from './components/Gathering'
import { Join, WhoAreYou } from './components/Join'
import { Picks } from './components/Picks'
import { Review } from './components/Review'
import { Start } from './components/Start'
import { Timeframe } from './components/Timeframe'
import { Working } from './components/Working'
import { count, monthDay } from './format'
import { ShellContext, type BoardTab } from './shell'
import { planningStarted } from './types'
import { useTrip } from './useTrip'

/** The trip lives in the URL hash, so a reload resumes it. Each traveler has their own link, `#<tripId>/<travelerId>`;
 *  `#<tripId>/join` is the invite link, and a bare `#<tripId>` asks who you are. */
function routeFromHash() {
  const [tripId, page] = window.location.hash.slice(1).split('/')
  return { tripId: tripId || null, joining: page === 'join', me: page && page !== 'join' ? page : null }
}

// The screens where the agents are all there is to watch: their board opens on the Agents tab.
const WATCHING = ['working', 'finding-dates']

export default function App() {
  const [{ tripId, joining, me }, setRoute] = useState(routeFromHash)
  const [finishing, setFinishing] = useState(false)
  const [editingPicks, setEditingPicks] = useState(false)
  const [rechoosing, setRechoosing] = useState(false)
  // Which side of the board is open, and the screen that was chosen on: every screen starts on its own default.
  const [board, setBoard] = useState<{ screen: string; tab: BoardTab; agent: string | null }>({ screen: '', tab: 'plan', agent: null })
  const { view, lanes, busy, sending, error, notice, act, setError, setNotice } = useTrip(tripId)

  useEffect(() => actAs(me), [me])

  useEffect(() => {
    const onHashChange = () => {
      setRoute(routeFromHash())
      setFinishing(false)
      setEditingPicks(false)
      setRechoosing(false)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  if (!tripId) {
    return <div className="app"><Start onCreated={(id, hostId) => { window.location.hash = `${id}/${hostId}` }} /></div>
  }

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
  const choosing = !!you && (stage === 'choosing' || stage === 'review') && (!you.confirmed || rechoosing)
  const optionsReady = !!you && (stage === 'review' || [`flight:${you.id}`, 'lodging'].every((agent) => {
    const status = state?.agents[agent]?.status
    return !!status && !['idle', 'working', 'under_review', 'sent_back'].includes(status)
  }))
  // Back undoes your last move in the app, or reopens the step before this one where that step can still change.
  // It never undoes what the agents have done, so it is disabled where there is nothing to go back to.
  const back =
    !you ? null
    : picking ? (you.picked ? () => setEditingPicks(false) : null)
    : beforePlanning ? () => setEditingPicks(true)
    : rechoosing ? () => setRechoosing(false)
    : stage !== 'review' || choosing ? null
    : finishing ? () => setFinishing(false)
    : () => setRechoosing(true)

  const screen =
    !view || !state ? 'loading'
    : joining ? 'join'
    : !you ? 'who'
    : picking ? 'picks'
    : choosing && optionsReady ? 'choose'
    : choosing || stage === 'choosing' || stage === 'planning' ? 'working'
    : stage === 'review' ? (finishing ? 'finish' : 'review')
    : stage === 'gathering' ? 'gathering'
    : stage === 'awaiting_dates' ? 'dates'
    : 'finding-dates'
  const onScreen = board.screen === screen
  // A choice made on another screen is forgotten, so coming back to that screen starts on its default again.
  if (board.screen && !onScreen) setBoard({ screen: '', tab: 'plan', agent: null })
  const tab = onScreen ? board.tab : WATCHING.includes(screen) ? 'agents' : 'plan'

  return (
    <div className="app">
      <header className="bar">
        <a className="brand" href="#">Tripwright</a>
        {state && (
          <>
            <span className="chip">{group < 2 && `${state.request.origin} → `}{state.request.destination}</span>
            <span className="chip">
              {state.dates ? `${monthDay(state.dates.start)} – ${monthDay(state.dates.end)}` : count(state.request.days, 'day')}
            </span>
            {group > 1 && <span className="chip">{group} travelers</span>}
          </>
        )}
        {you && <button className="pill sm" disabled={!back} onClick={() => back?.()}>← Back</button>}
        {state && working && <span className="working"><i className="st working" />Agents working…</span>}
        <span className="grow" />
        {you && (
          <span className="you">You: <b>{you.name}</b>{group > 1 && <> · <a href={`#${tripId}`}>Switch</a></>}</span>
        )}
        {you?.picked && beforePlanning && !editingPicks && (
          <button className="pill sm" onClick={() => setEditingPicks(true)}>Edit my picks</button>
        )}
        <a className="pill sm" href="#">New trip</a>
      </header>

      {(error || notice) && (
        <div className="banners">
          {error && (
            <div className="banner error" role="alert">
              <span>{error}</span>
              <button onClick={() => setError('')}>Dismiss</button>
            </div>
          )}
          {notice && (
            <div className="banner" role="status">
              <span>{notice}</span>
              <button onClick={() => setNotice('')}>Dismiss</button>
            </div>
          )}
        </div>
      )}

      {!view || !state ? (
        <>
          <main className="feed">{!error && <p className="say">Loading your trip…</p>}</main>
          <aside className="board" />
        </>
      ) : (
        <ShellContext.Provider
          value={{
            state, you: you ?? null, lanes, busy, tab,
            agent: onScreen ? board.agent : null,
            showTab: (next, agent) => setBoard({ screen, tab: next, agent: agent ?? null }),
            retry: () => act(api.retry(state.id)),
          }}
        >
          {/* Keyed by screen, so each one starts scrolled to its top with its own state. */}
          <Fragment key={screen}>
            {joining ? (
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
            ) : screen === 'picks' ? (
              <Picks
                state={state}
                you={you}
                busy={busy}
                onSave={async (picks) => {
                  const saved = await act(api.savePicks(state.id, you.id, picks))
                  if (saved) setEditingPicks(false)
                  return !!saved
                }}
                onAdd={async (name, city) => !!(await act(api.addIdea(state.id, name, city)))}
                onMore={async (picks) => !!(await act(api.suggestMore(state.id, picks)))}
              />
            ) : screen === 'choose' ? (
              <Choose
                key={you.id}
                state={state}
                you={you}
                sending={sending}
                onConfirm={async (flightId, stayIds) => {
                  if (await act(api.confirmChoices(state.id, you.id, flightId, stayIds))) setRechoosing(false)
                }}
              />
            ) : screen === 'working' ? (
              choosing ? (
                <Working state={state} title="Planning your flight and stays">
                  The agents are finding your flight and rooms. You'll choose them here as soon as they're ready.
                </Working>
              ) : stage === 'choosing' ? (
                <Working state={state} title="Planning activities around your choices">
                  The agents are still researching activities, transport and weather. Your days are planned around
                  your flight and rooms as soon as they finish.
                </Working>
              ) : (
                <Working state={state} title="Planning your trip">
                  Each specialist researches on its own. The orchestrator checks every result and sends back what
                  does not hold up.
                </Working>
              )
            ) : screen === 'finish' ? (
              <Finish
                view={view}
                you={you}
                busy={busy}
                onApprove={(card) => act(api.approvePayment(state.id, card))}
                onBackOut={() => act(api.backOut(state.id))}
              />
            ) : screen === 'review' ? (
              <Review
                view={view}
                you={you}
                busy={busy}
                onDecision={(action, card, optionId) => act(api.decide(state.id, action, card, optionId))}
                onApplyBudget={(travelerId) => act(api.applyBudget(state.id, travelerId))}
                onMove={(itemId, day) => act(api.moveItem(state.id, itemId, day))}
                onSwap={(itemId, attractionId) => act(api.swapItem(state.id, itemId, attractionId))}
                onFinish={() => setFinishing(true)}
              />
            ) : screen === 'gathering' ? (
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
              <Timeframe
                state={state}
                canChoose={you.host}
                busy={busy}
                onChoose={(start) => act(api.chooseDates(state.id, start))}
              />
            )}
          </Fragment>
        </ShellContext.Provider>
      )}
    </div>
  )
}
