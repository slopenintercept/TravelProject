import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { api } from './api'
import type { AgentStatus, TripEvent, TripView } from './types'

// --- agent lanes: built from state.agents on load, then kept current from the event stream ---

export interface LogEntry {
  kind: 'tool' | 'text' | 'sent_back'
  text: string
  detail?: string
}

export interface Lane extends AgentStatus {
  /** Reasons the orchestrator sent this agent's work back. Kept because `sent_back` is
   *  followed at once by `working` (or `fallback`), so the status alone is never on screen. */
  rejections: string[]
  log: LogEntry[]
}

export type Lanes = Record<string, Lane>

type LaneEvent = Extract<TripEvent, { agent: string }>
type LaneAction =
  | { type: 'clear' }
  | { type: 'replay' }
  | { type: 'seed'; agents: Record<string, AgentStatus> }
  | { type: 'event'; event: LaneEvent }

const LOG_LIMIT = 40

function compact(input: unknown): string {
  if (input === null || typeof input !== 'object') return String(input ?? '')
  return Object.entries(input)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`)
    .join(', ')
}

function reduceLanes(lanes: Lanes, action: LaneAction): Lanes {
  switch (action.type) {
    case 'clear':
      return {}
    case 'replay': // the stream replays its whole history on every (re)connect
      return Object.fromEntries(Object.entries(lanes).map(([name, lane]) => [name, { ...lane, rejections: [], log: [] }]))
    case 'seed': {
      const next = { ...lanes }
      for (const [name, status] of Object.entries(action.agents)) {
        if (!next[name] && status.status !== 'idle') next[name] = { ...status, rejections: [], log: [] }
      }
      return next
    }
    case 'event': {
      const event = action.event
      let lane: Lane = lanes[event.agent] ?? {
        agent: event.agent, status: 'working', attempt: 0, message: '', found: '', rejections: [], log: [],
      }
      let log = lane.log
      if (event.type === 'agent') {
        const { status, attempt, message, found } = event
        lane = { ...lane, status, attempt, message, found }
        if (status === 'sent_back') {
          lane.rejections = [...lane.rejections, message]
          log = [...log, { kind: 'sent_back', text: message }]
        }
      } else if (event.type === 'tool') {
        log = [...log, { kind: 'tool', text: event.tool, detail: compact(event.input) }]
      } else {
        const last = log[log.length - 1]
        log = last?.kind === 'text'
          ? [...log.slice(0, -1), { kind: 'text', text: last.text + event.text }]
          : [...log, { kind: 'text', text: event.text }]
      }
      return { ...lanes, [event.agent]: { ...lane, log: log.slice(-LOG_LIMIT) } }
    }
  }
}

// --- the trip itself -------------------------------------------------------------

export function useTrip(tripId: string | null) {
  const [view, setView] = useState<TripView | null>(null)
  const [lanes, dispatch] = useReducer(reduceLanes, {})
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const latest = useRef(0)

  /** Show a response unless a newer request has started since (responses can arrive out of order). */
  const load = useCallback(async (request: Promise<TripView>) => {
    const mine = ++latest.current
    const next = await request
    if (mine === latest.current) {
      setView(next)
      dispatch({ type: 'seed', agents: next.state.agents })
    }
    return next
  }, [])

  useEffect(() => {
    setView(null)
    setError('')
    setNotice('')
    dispatch({ type: 'clear' })
    if (!tripId) return

    const refresh = () => load(api.getTrip(tripId)).catch((e: Error) => setError(e.message))
    refresh()

    let timer: number | undefined
    const events = new EventSource(api.eventsUrl(tripId))
    events.onopen = () => dispatch({ type: 'replay' })
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as TripEvent
      if (event.type === 'state') {
        // One refetch for a burst of state events (the replay on connect sends them all at once).
        timer ??= window.setTimeout(() => {
          timer = undefined
          refresh()
        }, 100)
      } else if (event.type === 'error') {
        setError(event.message)
      } else if (event.type !== 'stage') {
        dispatch({ type: 'event', event })
      }
    }
    return () => {
      events.close()
      window.clearTimeout(timer)
      latest.current++ // drop responses still in flight for this trip
    }
  }, [tripId, load])

  /** Run a user action; `message` on the response is the server refusing it (for example a calendar move).
   *  Resolves to whether the request went through. */
  const act = useCallback(async (request: Promise<TripView>) => {
    setPending(true)
    setError('')
    setNotice('')
    try {
      setNotice((await load(request)).message)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setPending(false)
    }
  }, [load])

  return { view, lanes, busy: pending || !!view?.busy, error, notice, act, setError, setNotice }
}
