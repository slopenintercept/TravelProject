import { useEffect, useRef, useState } from 'react'
import { capitalize, count, money } from '../format'
import { useShell } from '../shell'
import type { AgentStatusName, Traveler, TripState } from '../types'
import type { Lane } from '../useTrip'

// Flights are found per traveler, and so are extra ideas: those lanes ("flight:<traveler>") go between these.
const BEFORE = ['route', 'profile', 'timeframe', 'ideas']
const AFTER = ['lodging', 'attractions', 'transport', 'weather', 'scheduler', 'budget', 'validate']
const RUNNING: AgentStatusName[] = ['working', 'under_review', 'sent_back']
const UNFINISHED: AgentStatusName[] = ['fallback', 'pending', 'failed']
const RESEARCH = /^(flight:|lodging$|attractions$|transport$|weather$)/

/** "validate" reads "Validate agent"; "flight:p2" reads "Flight agent · Sam", or just "Flight agent" on a solo trip. */
export function agentName(agent: string, travelers: Traveler[]): string {
  const [role, travelerId] = agent.split(':')
  const traveler = travelers.length > 1 && travelers.find((t) => t.id === travelerId)
  const name = `${capitalize(role.replace(/_/g, ' '))} agent`
  return traveler ? `${name} · ${traveler.name}` : name
}

// The dot beside an agent's name, and the word for its status on the Agents tab.
const DOT: Record<AgentStatusName, string> = {
  idle: 'idle', working: 'working', under_review: 'review', sent_back: 'bad',
  accepted: '', fallback: 'bad', pending: 'bad', failed: 'bad',
}
const WORD: Record<AgentStatusName, string> = {
  idle: 'Waiting', working: 'Working', under_review: 'Under review', sent_back: 'Sent back',
  accepted: 'Accepted', fallback: 'Saved result', pending: "Didn't finish", failed: 'Failed',
}

/** How often the orchestrator sent this agent's work back. The reasons come from the event stream, which a
 *  server restart forgets; the attempt number is saved with the trip. */
const sentBack = (lane: Lane) => Math.max(lane.rejections.length, lane.attempt - 1)

/** What an agent is doing, when it has not finished cleanly. */
function doing(lane: Lane | undefined): string | null {
  switch (lane?.status) {
    case 'accepted': return null
    case 'working': return sentBack(lane) > 0 ? 'sent back, trying again' : 'working…'
    case 'under_review': return 'under review'
    case 'sent_back': return 'sent back, trying again'
    case 'fallback': return 'saved result'
    case 'pending': return "didn't finish"
    case 'failed': return 'failed'
    default: return 'waiting'
  }
}

const brief = (text: string) => (text.length > 48 ? `${text.slice(0, 47).trimEnd()}…` : text)

/** A few words on what an agent found, from the numbers the trip already holds. */
function found(agent: string, state: TripState, you: Traveler | null): string | undefined {
  const [role, travelerId] = agent.split(':')
  const group = state.travelers.length
  const visits = (items: { kind: string }[]) => items.filter((i) => i.kind === 'attraction').length

  switch (role) {
    case 'ideas':
      return count(state.ideas.length, 'place')
    case 'timeframe':
      return state.windows.length ? count(state.windows.length, 'date window') : undefined
    case 'draft':
      return state.draft
        ? `${count(visits(state.draft.itinerary), 'activity', 'activities')} from ${group > 1 ? "everyone's" : 'your'} picks`
        : undefined
    case 'flight': {
      const options = state.travelers.find((t) => t.id === travelerId)?.flights?.options.length
      return options ? (options > 1 ? `best of ${options} options` : '1 option') : undefined
    }
    case 'attractions':
      return state.attractions.length ? count(state.attractions.length, 'attraction') : undefined
    case 'lodging': {
      const stays = state.lodging?.stays ?? []
      if (stays.length === 0) return undefined
      const each = stays[0].options.length
      return stays.length > 1 && stays.every((s) => s.options.length === each)
        ? `${count(each, 'option')} a stay`
        : count(stays.reduce((sum, s) => sum + s.options.length, 0), 'option')
    }
    case 'transport': {
      const legs = (you ?? state.travelers[0])?.legs.filter((leg) => leg.included) ?? []
      return legs.length ? `${count(legs.length, 'leg')}, ${money(legs.reduce((sum, leg) => sum + leg.price_usd, 0))}` : undefined
    }
    case 'scheduler': {
      if (state.itinerary.length === 0) return undefined
      const missed = state.unscheduled.length
      return `${visits(state.itinerary)} placed${missed ? `, ${missed} didn't fit` : ''}`
    }
    case 'budget': {
      const over = state.travelers.filter((t) => (state.budgets[t.id]?.remaining_usd ?? 0) < 0).length
      if (Object.keys(state.budgets).length === 0) return undefined
      if (group < 2) return over ? 'over budget' : 'within budget'
      if (over === 0) return 'everyone within budget'
      return over < group ? `${over} of ${group} over` : group === 2 ? 'both travelers over' : 'everyone over'
    }
    case 'validate': {
      const issues = state.violations.length
      if (issues === 0) return 'no issues'
      // Another traveler's budget is theirs to fix; everything else needs whoever is looking.
      const budgets = state.violations.filter((v) => v.code === 'OVER_BUDGET').length
      const mine = you && (state.budgets[you.id]?.remaining_usd ?? 0) < 0 ? 1 : 0
      return group > 1 && you ? `${count(issues, 'issue')}, ${issues - budgets + mine} yours` : count(issues, 'issue')
    }
  }
}

interface TagProps {
  agent: string
  /** What it found, where the headline is about part of its work ("4 found" in one category). */
  words?: string
}

/** The agent behind a headline: its status dot, its name, and a few words on what it found or is doing.
 *  Clicking it opens that agent on the board's Agents tab. */
export function AgentTag({ agent, words }: TagProps) {
  const { state, you, lanes, showTab } = useShell()
  const lane = lanes[agent]
  return (
    <button className="by" title="Show what this agent did" onClick={() => showTab('agents', agent)}>
      <i className={`st ${DOT[lane?.status ?? 'idle']}`} />
      <b>{agentName(agent, state.travelers)}</b>
      <span>{doing(lane) ?? words ?? found(agent, state, you) ?? brief(lane.found)}</span>
    </button>
  )
}

function LaneCard({ lane, name, selected, detailed }: { lane: Lane; name: string; selected: boolean; detailed: boolean }) {
  const card = useRef<HTMLElement>(null)
  const log = useRef<HTMLOListElement>(null)
  useEffect(() => {
    if (selected) card.current?.scrollIntoView({ block: 'nearest' })
  }, [selected])
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight
  }, [lane.log, detailed])

  const dot = DOT[lane.status]
  const rejected = sentBack(lane)
  const accepted = lane.status === 'accepted'
  return (
    <article ref={card} className={selected ? 'lane sel' : 'lane'}>
      <header>
        <i className={`st ${dot}`} />
        <b>{name}</b>
        <span className={`stp ${dot}`}>{WORD[lane.status]}</span>
      </header>
      {lane.found && <p>{lane.found}</p>}
      {(!accepted || detailed) && lane.message && lane.status !== 'sent_back' && <p>{lane.message}</p>}
      {/* keyed so the flash replays on every rejection */}
      {rejected > 0 && (
        <p key={rejected} className={accepted ? undefined : 'sent'}>
          Sent back by the orchestrator {rejected === 1 ? 'once' : rejected === 2 ? 'twice' : `${rejected} times`}.
          {accepted && ` Accepted on attempt ${lane.attempt}.`}
        </p>
      )}
      {detailed && lane.rejections.map((reason, i) => <p key={i}>Sent back: {reason}</p>)}
      {detailed && lane.log.length > 0 && (
        <ol className="log" ref={log}>
          {lane.log.map((entry, i) => (
            <li key={i} className={entry.kind}>
              {entry.kind === 'tool' ? <><code>{entry.text}</code> {entry.detail}</>
                : entry.kind === 'sent_back' ? `Sent back: ${entry.text}`
                : entry.text}
            </li>
          ))}
        </ol>
      )}
    </article>
  )
}

/** The lanes in the order the agents run. */
export function laneOrder(lanes: Record<string, Lane>, travelers: Traveler[]): string[] {
  const per = (role: string) => travelers.map((t) => `${role}:${t.id}`)
  const order = [...BEFORE, ...per('more_ideas'), 'draft', ...per('flight'), ...AFTER]
  return [...order, ...Object.keys(lanes).filter((name) => !order.includes(name))].filter((name) => lanes[name])
}

/** The board's Agents tab: one card per agent, with what it found. The orchestrator's rejections and each agent's
 *  tool log sit behind "Show details", and always show on the card a headline's tag opened. */
export function AgentLanes({ detailed = false }: { detailed?: boolean }) {
  const { state, lanes, agent: selected, busy, retry } = useShell()
  const [choice, setChoice] = useState<boolean | null>(null)
  const details = choice ?? detailed
  const names = laneOrder(lanes, state.travelers)
  const running = names.filter((name) => RUNNING.includes(lanes[name].status)).length
  const unfinished = names.filter((name) => RESEARCH.test(name) && UNFINISHED.includes(lanes[name].status))
  const howMany = unfinished.length === 1 ? 'one' : unfinished.length

  return (
    <section aria-label="Agents">
      <header className="ag-head">
        <span>
          {names.length === 0 ? 'Waiting for the first agent to start…'
            : running > 1 ? `${running} agents running in parallel`
            : running === 1 ? '1 agent running'
            : 'No agents running'}
        </span>
        <span className="grow" />
        {unfinished.length > 0 && running === 0 && (
          <button
            className="pill sm solid"
            disabled={busy}
            onClick={retry}
            title={unfinished.map((name) => agentName(name, state.travelers)).join(', ')}
          >
            Retry the {howMany} that didn't finish
          </button>
        )}
        {names.length > 0 && (
          <button className="pill sm" aria-pressed={details} onClick={() => setChoice(!details)}>
            {details ? 'Hide details' : 'Show details'}
          </button>
        )}
      </header>
      <div className="ag-lanes">
        {names.map((name) => (
          <LaneCard
            key={name}
            lane={lanes[name]}
            name={agentName(name, state.travelers)}
            selected={name === selected}
            detailed={details || name === selected}
          />
        ))}
      </div>
    </section>
  )
}
