import type { ReactNode } from 'react'
import { useShell } from '../shell'
import type { TripState } from '../types'
import { AgentTag, laneOrder } from './Agents'
import { Board } from './Board'
import { DraftPlan } from './DraftPlan'

/** One line per agent as it reports. Each opens that agent on the board. */
export function Crew() {
  const { state, lanes } = useShell()
  const names = laneOrder(lanes, state)
  if (names.length === 0) return <p className="small">Waiting for the first agent to start…</p>
  return <div className="crew">{names.map((name) => <AgentTag key={name} agent={name} />)}</div>
}

interface Props {
  state: TripState
  title: string
  children: ReactNode
}

/** The agents are working and there is nothing to decide yet: the feed lists them, the board shows their logs. */
export function Working({ state, title, children }: Props) {
  return (
    <>
      <main className="feed">
        <div className="hd top"><h1 className="display h-40">{title}</h1></div>
        <p className="say">{children}</p>
        <Crew />
      </main>
      <Board plan="Draft plan" detailed>
        <DraftPlan state={state} />
      </Board>
    </>
  )
}
