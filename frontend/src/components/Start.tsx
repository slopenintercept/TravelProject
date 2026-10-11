import { useState, type FormEvent, type ReactNode } from 'react'
import { api } from '../api'
import { tomorrow } from '../format'
import type { Pace } from '../types'
import { EmptyPlan } from './Route'

const PACES: Pace[] = ['relaxed', 'balanced', 'packed']

const EMPTY = {
  name: '', origin: '', destination: '', days: '', start_date: '', budget_usd: '', pace: 'balanced' as Pace,
}
const DEMO: typeof EMPTY = {
  ...EMPTY, name: 'Alex', origin: 'Kansas City', destination: 'Japan', days: '7', budget_usd: '2500',
}

/** One question in a form card: the question on the left, its answer on the right. */
export function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="row">
      <span>{label}{hint && <small>{hint}</small>}</span>
      {children}
    </label>
  )
}

/** Where a trip starts: the host's form on the left, and the empty plan it will fill on the right. */
export function Start({ onCreated }: { onCreated: (tripId: string, hostId: string) => void }) {
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
        pace: form.pace,
      })
      onCreated(view.state.id, view.state.travelers[0].id)
    } catch (err) {
      setError((err as Error).message)
      setSending(false)
    }
  }

  return (
    <>
      <header className="bar">
        <a className="brand" href="#">Tripwright</a>
        <span className="grow" />
        <button className="pill sm" onClick={() => setForm(DEMO)}>Use the demo trip</button>
      </header>
      {error && <div className="banners"><p className="banner error" role="alert">{error}</p></div>}

      <main className="feed">
        <div className="hd top"><h1 className="display hero">Plan a trip.</h1></div>
        <p className="lede">
          A team of agents researches it in parallel. Next you'll pick what sounds good from the places they find,
          then review every choice and do the booking yourself.
        </p>
        <form onSubmit={submit}>
          <div className="card ticket">
            <Row label="Your name">
              <input className="field" required value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="Alex" />
            </Row>
            <Row label="Where are you traveling from?">
              <input className="field" required value={form.origin} onChange={(e) => set({ origin: e.target.value })} placeholder="Kansas City" />
            </Row>
            <Row label="Where do you want to go?">
              <input className="field" required value={form.destination} onChange={(e) => set({ destination: e.target.value })} placeholder="Japan" />
            </Row>
            <Row label="How long do you want to stay?" hint="Days, 1 to 30">
              <input className="field" required type="number" min={1} max={30} value={form.days} onChange={(e) => set({ days: e.target.value })} placeholder="7" />
            </Row>
            <Row label="When do you want to go?" hint="Optional. Blank lets the agents suggest dates.">
              <input className={form.start_date ? 'field' : 'field blank'} type="date" min={tomorrow()} value={form.start_date} onChange={(e) => set({ start_date: e.target.value })} />
            </Row>
            <Row label="What's your total budget?" hint="US dollars, for the whole trip">
              <input className="field" required type="number" min={1} step="any" value={form.budget_usd} onChange={(e) => set({ budget_usd: e.target.value })} placeholder="2500" />
            </Row>
            <div className="row" role="radiogroup" aria-labelledby="pace-label">
              <span id="pace-label">How packed should the itinerary be?</span>
              <span className="seg">
                {PACES.map((pace) => (
                  <label key={pace}>
                    <input type="radio" name="pace" checked={form.pace === pace} onChange={() => set({ pace })} />
                    <span>{pace}</span>
                  </label>
                ))}
              </span>
            </div>
          </div>
          <div className="go">
            <button className="pill solid xl wide" disabled={sending}>{sending ? 'Starting the agents…' : 'Start planning →'}</button>
          </div>
        </form>
      </main>

      <aside className="board">
        <EmptyPlan days={Number(form.days)} />
      </aside>
    </>
  )
}
