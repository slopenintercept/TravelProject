import { useState, type FormEvent } from 'react'
import { commaList } from '../format'
import type { TravelerIn } from '../types'
import { Field } from './TripForm'

const EMPTY = { name: '', origin: '', budget_usd: '', need: '', want: '' }

const LABELS = {
  you: {
    name: 'Your name', origin: 'Where are you traveling from?', budget: "What's your budget?",
    need: 'What do you need to see?', want: 'What would you like to see?', submit: 'Join the trip',
  },
  them: {
    name: 'Their name', origin: 'Where are they traveling from?', budget: "What's their budget?",
    need: 'What do they need to see?', want: 'What would they like to see?', submit: 'Add traveler',
  },
}

interface Props {
  /** The host is filling this in for someone else. */
  them?: boolean
  busy: boolean
  /** Resolves to whether the traveler was added. */
  onSubmit: (traveler: TravelerIn) => Promise<boolean>
}

/** What each traveler fills in to join a trip. */
export function TravelerForm({ them = false, busy, onSubmit }: Props) {
  const [form, setForm] = useState(EMPTY)
  const set = (patch: Partial<typeof EMPTY>) => setForm((current) => ({ ...current, ...patch }))
  const label = them ? LABELS.them : LABELS.you

  async function submit(e: FormEvent) {
    e.preventDefault()
    const added = await onSubmit({
      name: form.name.trim(),
      origin: form.origin.trim(),
      budget_usd: Number(form.budget_usd),
      need: commaList(form.need),
      want: commaList(form.want),
    })
    if (added) setForm(EMPTY)
  }

  return (
    <form onSubmit={submit}>
      <div className="fields">
        <Field label={label.name}>
          <input required value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="Sam" />
        </Field>
        <Field label={label.origin}>
          <input required value={form.origin} onChange={(e) => set({ origin: e.target.value })} placeholder="Denver" />
        </Field>
        <Field label={label.budget} hint="US dollars, for the whole trip">
          <input required type="number" min={1} step="any" value={form.budget_usd} onChange={(e) => set({ budget_usd: e.target.value })} placeholder="2500" />
        </Field>
        <Field label={label.need} hint="Optional. Separate them with commas.">
          <input value={form.need} onChange={(e) => set({ need: e.target.value })} placeholder="Tokyo Disneyland, Kyoto" />
        </Field>
        <Field label={label.want} hint="Optional. Separate them with commas.">
          <input value={form.want} onChange={(e) => set({ want: e.target.value })} placeholder="teamLab Planets" />
        </Field>
      </div>
      <button className={them ? undefined : 'primary big'} disabled={busy}>{label.submit}</button>
    </form>
  )
}
