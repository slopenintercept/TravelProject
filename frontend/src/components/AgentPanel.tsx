import { useEffect, useRef, useState } from 'react'
import type { Traveler } from '../types'
import type { Lane, Lanes } from '../useTrip'

// Flights are found per traveler: those lanes ("flight:<traveler>") go between these.
const BEFORE = ['route', 'profile', 'timeframe']
const AFTER = ['lodging', 'attractions', 'transport', 'weather', 'scheduler', 'budget', 'validate']

/** "flight:p2" reads "flight · Sam"; with one traveler it is just "flight". */
function title(agent: string, travelers: Traveler[]): string {
  const [role, travelerId] = agent.split(':')
  const traveler = travelers.length > 1 && travelers.find((t) => t.id === travelerId)
  return traveler ? `${role} · ${traveler.name}` : role
}

function LaneCard({ lane, title, detailed }: { lane: Lane; title: string; detailed: boolean }) {
  const log = useRef<HTMLOListElement>(null)
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight
  }, [lane.log, detailed])

  const rejected = lane.rejections.length
  return (
    <article className={`lane status-${lane.status}`}>
      <header>
        <h3>{title}</h3>
        {lane.attempt > 1 && <span className="attempt">attempt {lane.attempt}</span>}
        <span className={`pill status-${lane.status}`}>{lane.status.replace('_', ' ')}</span>
      </header>

      {/* keyed so the flash replays on every rejection */}
      {rejected > 0 && (
        <p key={rejected} className="sent-back">
          <strong>Sent back by the orchestrator{rejected > 1 && ` ×${rejected}`}</strong>
          {detailed && lane.rejections[rejected - 1]}
        </p>
      )}
      {detailed && lane.message && lane.status !== 'sent_back' && <p>{lane.message}</p>}
      {detailed && lane.found && <p className="found">{lane.found}</p>}

      {detailed && lane.log.length > 0 && (
        <ol className="log" ref={log}>
          {lane.log.map((entry, i) => (
            <li key={i} className={`log-${entry.kind}`}>
              {entry.kind === 'tool' ? (
                <>
                  <code>{entry.text}</code> {entry.detail}
                </>
              ) : entry.kind === 'sent_back' ? (
                `Sent back: ${entry.text}`
              ) : (
                entry.text
              )}
            </li>
          ))}
        </ol>
      )}
    </article>
  )
}

const RESEARCH = /^(flight:|lodging$|attractions$|transport$|weather$)/

interface Props {
  lanes: Lanes
  travelers: Traveler[]
  /** Start the lanes as one-line chips (name and status). */
  compact?: boolean
  /** Run again the research agents that timed out or fell back to saved results. */
  onRetry?: () => void
  busy?: boolean
}

/** One lane per agent, side by side. */
export function AgentPanel({ lanes, travelers, compact = false, onRetry, busy }: Props) {
  const [choice, setChoice] = useState<boolean | null>(null)
  const detailed = choice ?? !compact
  const order = [...BEFORE, ...travelers.map((t) => `flight:${t.id}`), ...AFTER]
  const names = [...order, ...Object.keys(lanes).filter((name) => !order.includes(name))].filter((name) => lanes[name])
  const running = names.filter((name) => ['working', 'under_review', 'sent_back'].includes(lanes[name].status)).length
  const unfinished = names.filter((name) => RESEARCH.test(name) && ['fallback', 'pending', 'failed'].includes(lanes[name].status))

  return (
    <section className={detailed ? 'agents detailed' : 'agents'}>
      <header className="agents-head">
        <h2>Agent activity</h2>
        <span className="muted">
          {names.length === 0
            ? 'Waiting for the first agent to start…'
            : running > 1
              ? `${running} agents running in parallel`
              : running === 1
                ? '1 agent running'
                : 'No agents running'}
        </span>
        {names.length > 0 && (
          <button className="link" onClick={() => setChoice(!detailed)}>{detailed ? 'Hide details' : 'Show details'}</button>
        )}
        {onRetry && unfinished.length > 0 && running === 0 && (
          <button
            disabled={busy}
            onClick={onRetry}
            aria-label={`Retry the ${unfinished.length === 1 ? 'one' : unfinished.length} that didn't finish`}
            title={unfinished.map((n) => title(n, travelers)).join(', ')}
          >
            Retry the {unfinished.length === 1 ? 'one' : unfinished.length} that didn't finish
          </button>
        )}
      </header>
      <div className="lanes">
        {names.map((name) => <LaneCard key={name} lane={lanes[name]} title={title(name, travelers)} detailed={detailed} />)}
      </div>
    </section>
  )
}
