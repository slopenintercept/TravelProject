import { useRef, useState } from 'react'
import { money } from '../format'
import type { TravelerIn, TripState } from '../types'
import { Chips } from './Chips'
import { TravelerForm } from './TravelerForm'

interface Props {
  state: TripState
  busy: boolean
  onAdd: (traveler: TravelerIn) => Promise<boolean>
  onRemove: (travelerId: string) => void
  onPlan: () => void
}

/** Dates are set: the host invites the other travelers, then starts planning once everyone is in. */
export function Gathering({ state, busy, onAdd, onRemove, onPlan }: Props) {
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
        Send the invite link to everyone on the trip. Each traveler adds where they fly from, their budget and what
        they need and want to see. The agents then find flights and lodging for each traveler, and plan the
        attractions for the group.
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
              {t.host ? (
                <span className="pill">host</span>
              ) : (
                <button disabled={busy} onClick={() => onRemove(t.id)}>Remove</button>
              )}
            </header>
            <p className="muted">Flying from {t.origin} · {money(t.budget_usd)} budget</p>
            <Chips label="Needs to see" items={t.need} />
            <Chips label="Wants to see" items={t.want} />
          </li>
        ))}
      </ul>

      <section className="add-traveler panel">
        <h2>Add a traveler here</h2>
        <TravelerForm them busy={busy} onSubmit={onAdd} />
      </section>

      <button className="primary big" disabled={busy} onClick={onPlan}>Everyone's in: plan the trip</button>
    </section>
  )
}
