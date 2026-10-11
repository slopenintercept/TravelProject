import { useRef, useState } from 'react'
import { money } from '../format'
import type { Traveler, TripState } from '../types'
import { Board } from './Board'
import { Chips } from './Chips'
import { DraftPlan } from './DraftPlan'

interface Props {
  state: TripState
  you: Traveler
  busy: boolean
  onRemove: (travelerId: string) => void
  onPlan: () => void
}

/** Dates are set: the host invites the other travelers, who each join from their own device with the link.
 *  The host starts planning once everyone is in. */
export function Gathering({ state, you, busy, onRemove, onPlan }: Props) {
  const [copied, setCopied] = useState(false)
  const linkInput = useRef<HTMLInputElement>(null)
  const link = `${location.origin}${location.pathname}#${state.id}/join`

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
    } catch {
      linkInput.current?.select() // no clipboard access (for example over plain http): ready to copy by hand
    }
  }

  return (
    <>
      <main className="feed">
        <div className="hd top"><h1 className="display h-40">Who's coming?</h1></div>
        <p className="say">
          Send the invite link to everyone on the trip. Each traveler opens it on their own device, adds where they
          fly from and their budget, and marks what they want to do. The agents then find flights and lodging for
          each traveler, and plan the days for the group.
        </p>

        <div className="invite">
          <label className="cap" htmlFor="invite-link">Invite link</label>
          <input id="invite-link" className="field" ref={linkInput} readOnly value={link} onFocus={(e) => e.target.select()} />
          <button className="pill" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
        </div>

        {state.travelers.map((t) => (
          <article key={t.id} className="card person">
            <header>
              <h3>{t.name}</h3>
              {t.id === you.id && <span className="chip">You</span>}
              {t.host ? (
                <span className="chip">Host</span>
              ) : (you.host || t.id === you.id) && (
                <button className="pill sm" disabled={busy} onClick={() => onRemove(t.id)}>{t.id === you.id ? 'Leave' : 'Remove'}</button>
              )}
            </header>
            <p className="small">
              Flying from {t.origin} · {money(t.budget_usd)} budget{!t.picked && " · hasn't picked places yet"}
            </p>
            <Chips label="Must do" items={t.need} />
            <Chips label="Interested" items={t.want} />
            <Chips label="Not for them" items={t.skip} />
          </article>
        ))}

        {you.host ? (
          <div className="go">
            <button className="pill solid xl wide" disabled={busy} onClick={onPlan}>Everyone's in: plan the trip →</button>
          </div>
        ) : (
          <p className="lede">Waiting for {state.travelers.find((t) => t.host)?.name ?? 'the host'} to start planning.</p>
        )}
      </main>

      <Board plan="Draft plan">
        <DraftPlan state={state} musts={you.need} />
      </Board>
    </>
  )
}
