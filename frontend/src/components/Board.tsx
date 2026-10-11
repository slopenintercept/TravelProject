import type { ReactNode } from 'react'
import { useShell } from '../shell'
import { AgentLanes } from './Agents'

interface BoardProps {
  /** What the plan side is called on this screen: "Draft plan", "Your days". */
  plan: string
  /** Open the agents' logs from the start (the screens where the agents are what there is to watch). */
  detailed?: boolean
  children: ReactNode
}

/** The plan panel: the plan itself, or the agents behind it. */
export function Board({ plan, detailed, children }: BoardProps) {
  const { lanes, tab, showTab } = useShell()
  const all = Object.values(lanes)
  const unfinished = all.some((lane) => ['fallback', 'pending', 'failed'].includes(lane.status))

  return (
    <aside className="board">
      <div className="view board-tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'plan'} onClick={() => showTab('plan')}>{plan}</button>
        <button role="tab" aria-selected={tab === 'agents'} onClick={() => showTab('agents')}>
          {unfinished && <i className="st bad" title="Some agents didn't finish" />}Agents · {all.length}
        </button>
      </div>
      {/* Hidden, not unmounted: the plan keeps its state (who the calendar shows) while the agents are open. */}
      <div className="board-main" hidden={tab !== 'plan'}>{children}</div>
      {tab === 'agents' && <AgentLanes detailed={detailed} />}
    </aside>
  )
}
