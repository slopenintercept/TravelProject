import { useState, type FormEvent } from 'react'
import type { TravelerIn } from '../types'
import { Field } from './TripForm'

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
      <div className="fields">
        <Field label="Your name">
          <input required value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="Sam" />
        </Field>
        <Field label="Where are you traveling from?">
          <input required value={form.origin} onChange={(e) => set({ origin: e.target.value })} placeholder="Denver" />
        </Field>
        <Field label="What's your budget?" hint="US dollars, for the whole trip">
          <input required type="number" min={1} step="any" value={form.budget_usd} onChange={(e) => set({ budget_usd: e.target.value })} placeholder="2500" />
        </Field>
      </div>
      <p className="muted">Next, you'll pick what you want to do from places the agents found.</p>
      <button className="primary big" disabled={busy}>Join the trip</button>
    </form>
  )
}
