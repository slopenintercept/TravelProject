import { useRef, useState } from 'react'
import { money } from '../format'
import type { Traveler, TripState } from '../types'
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
    <section className="gathering">
      <h1>Who's coming?</h1>
      <p className="lede">
        Send the invite link to everyone on the trip. Each traveler opens it on their own device, adds where they fly
        from and their budget, and marks what they want to do on the list of places. The agents then find flights and
        lodging for each traveler, and plan the days for the group. Everyone reviews their own flight and stays.
      </p>

      <div className="invite panel">
        <label htmlFor="invite-link">Invite link</label>
        <input id="invite-link" ref={linkInput} readOnly value={link} onFocus={(e) => e.target.select()} />
        <button onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
      </div>

      <ul className="travelers">
        {state.travelers.map((t) => (
          <li key={t.id} className="traveler panel">
            <header>
              <h3>{t.name}</h3>
              {t.id === you.id && <span className="pill">you</span>}
              {t.host ? (
                <span className="pill">host</span>
              ) : (you.host || t.id === you.id) && (
                <button disabled={busy} onClick={() => onRemove(t.id)}>{t.id === you.id ? 'Leave' : 'Remove'}</button>
              )}
            </header>
            <p className="muted">Flying from {t.origin} · {money(t.budget_usd)} budget</p>
            {!t.picked && <p className="muted">Hasn't picked places yet</p>}
            <Chips label="Must do" items={t.need} />
            <Chips label="Interested" items={t.want} />
            <Chips label="Not for them" items={t.skip} />
          </li>
        ))}
      </ul>

      <DraftPlan state={state} you={you} />

      {you.host ? (
        <button className="primary big" disabled={busy} onClick={onPlan}>Everyone's in: plan the trip</button>
      ) : (
        <p className="lede">Waiting for {state.travelers.find((t) => t.host)?.name ?? 'the host'} to start planning.</p>
      )}
    </section>
  )
}
