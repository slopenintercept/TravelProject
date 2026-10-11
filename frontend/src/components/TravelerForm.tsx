import { useState, type FormEvent } from 'react'
import type { TravelerIn } from '../types'
import { Row } from './Start'

const EMPTY = { name: '', origin: '', budget_usd: '' }

interface Props {
  busy: boolean
  /** Resolves to whether the traveler was added. */
  onSubmit: (traveler: TravelerIn) => Promise<boolean>
}

/** What each traveler fills in, on their own device, to join a trip. */
export function TravelerForm({ busy, onSubmit }: Props) {
  const [form, setForm] = useState(EMPTY)
  const set = (patch: Partial<typeof EMPTY>) => setForm((current) => ({ ...current, ...patch }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    const added = await onSubmit({
      name: form.name.trim(),
      origin: form.origin.trim(),
      budget_usd: Number(form.budget_usd),
    })
    if (added) setForm(EMPTY)
  }

  return (
    <form onSubmit={submit}>
      <div className="card ticket">
        <Row label="Your name">
          <input className="field" required value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="Sam" />
        </Row>
        <Row label="Where are you traveling from?">
          <input className="field" required value={form.origin} onChange={(e) => set({ origin: e.target.value })} placeholder="Denver" />
        </Row>
        <Row label="What's your budget?" hint="US dollars, for the whole trip">
          <input className="field" required type="number" min={1} step="any" value={form.budget_usd} onChange={(e) => set({ budget_usd: e.target.value })} placeholder="2500" />
        </Row>
      </div>
      <div className="go"><button className="pill solid xl wide" disabled={busy}>Join the trip →</button></div>
      <p className="aside">Next, you'll pick what you want to do from places the agents found.</p>
    </form>
  )
}
