import { createContext, useContext } from 'react'
import type { Traveler, TripState } from './types'
import type { Lanes } from './useTrip'

export type BoardTab = 'plan' | 'agents'

/** What every screen of a trip shares: the trip, who is looking, the agents, and which side of the board is open. */
export interface Shell {
  state: TripState
  you: Traveler | null
  lanes: Lanes
  busy: boolean
  tab: BoardTab
  /** The agent highlighted on the Agents tab. */
  agent: string | null
  /** Switch the board; naming an agent opens the Agents tab on its card. */
  showTab: (tab: BoardTab, agent?: string) => void
  /** Run again the research agents that timed out or fell back to saved results. */
  retry: () => void
}

export const ShellContext = createContext<Shell | null>(null)

export function useShell(): Shell {
  const shell = useContext(ShellContext)
  if (!shell) throw new Error('useShell needs a trip')
  return shell
}
