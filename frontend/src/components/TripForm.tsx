import { useState, type FormEvent, type ReactNode } from 'react'
import { api } from '../api'
import { commaList, tomorrow } from '../format'
import type { Pace } from '../types'

const PACES: Pace[] = ['relaxed', 'balanced', 'packed']

const EMPTY = {
  name: '', origin: '', destination: '', days: '', start_date: '', budget_usd: '', need: '', want: '',
  pace: 'balanced' as Pace,
}
const DEMO: typeof EMPTY = {
  ...EMPTY, name: 'Alex', origin: 'Kansas City', destination: 'Japan', days: '7', budget_usd: '2500',
  need: 'Tokyo Disneyland, Kyoto', want: 'teamLab Planets',
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

export function TripForm({ onCreated }: { onCreated: (tripId: string) => void }) {
  const [form, setForm] = useState(EMPTY)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const set = (patch: Partial<typeof EMPTY>) => setForm((current) => ({ ...current, ...patch }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSending(true)
    setError('')
    try {
      const view = await api.createTrip({
        name: form.name.trim(),
        origin: form.origin.trim(),
        destination: form.destination.trim(),
        days: Number(form.days),
        start_date: form.start_date || null,
        budget_usd: Number(form.budget_usd),
        need: commaList(form.need),
        want: commaList(form.want),
        pace: form.pace,
      })
      onCreated(view.state.id)
    } catch (err) {
      setError((err as Error).message)
      setSending(false)
    }
  }

  return (
    <form className="trip-form panel" onSubmit={submit}>
      <div className="form-head">
        <div>
          <h1>Plan a trip</h1>
          <p className="lede">A team of agents researches it in parallel. You review every choice and do the booking yourself.</p>
        </div>
        <button type="button" onClick={() => setForm(DEMO)}>Use the demo trip</button>
      </div>

      <div className="fields">
        <Field label="Your name">
          <input required value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="Alex" />
        </Field>
        <Field label="Where are you traveling from?">
          <input required value={form.origin} onChange={(e) => set({ origin: e.target.value })} placeholder="Kansas City" />
        </Field>
        <Field label="Where do you want to go?">
          <input required value={form.destination} onChange={(e) => set({ destination: e.target.value })} placeholder="Japan" />
        </Field>
        <Field label="How long do you want to stay?" hint="Days, 1 to 30">
          <input required type="number" min={1} max={30} value={form.days} onChange={(e) => set({ days: e.target.value })} placeholder="7" />
        </Field>
        <Field label="When do you want to go?" hint="Optional. Leave it blank and the agents will suggest the best dates.">
          <input type="date" min={tomorrow()} value={form.start_date} onChange={(e) => set({ start_date: e.target.value })} />
        </Field>
        <Field label="What's your total budget?" hint="US dollars, for the whole trip">
          <input required type="number" min={1} step="any" value={form.budget_usd} onChange={(e) => set({ budget_usd: e.target.value })} placeholder="2500" />
        </Field>
        <Field label="What do you need to see?" hint="Optional. Separate them with commas.">
          <input value={form.need} onChange={(e) => set({ need: e.target.value })} placeholder="Tokyo Disneyland, Kyoto" />
        </Field>
        <Field label="What would you like to see?" hint="Optional. Separate them with commas.">
          <input value={form.want} onChange={(e) => set({ want: e.target.value })} placeholder="teamLab Planets" />
        </Field>
        <fieldset className="field">
          <legend>How packed should the itinerary be?</legend>
          <div className="segmented">
            {PACES.map((pace) => (
              <label key={pace}>
                <input type="radio" name="pace" checked={form.pace === pace} onChange={() => set({ pace })} />
                <span>{pace}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {error && <p className="banner error" role="alert">{error}</p>}
      <button className="primary big" disabled={sending}>{sending ? 'Starting the agents…' : 'Plan my trip'}</button>
    </form>
  )
}
