import { money, safeHref, whoIsIn } from '../format'
import type { BookingStep, Category, TripView } from '../types'
import { Chips } from './Chips'

/** What the group books together; each traveler's own flight and stays come first. */
const SHARED: [Category, string][] = [
  ['attractions', 'Tickets'],
  ['transport', 'Getting around'],
]

const LINK_LABEL: Record<BookingStep['link'], string> = {
  filled: 'Open with details filled in',
  booking: 'Open the booking page',
  info: 'See how to buy',
}

interface Props {
  view: TripView
  onBack: () => void
}

/** The hand-off: everything to book, in order, each with a link that already carries the trip's details. */
export function Finish({ view, onBack }: Props) {
  const { booking, state } = view
  const { travelers } = state
  const solo = travelers.length < 2
  const total = booking.reduce((sum, step) => sum + step.price_usd, 0)
  const budget = travelers.reduce((sum, t) => sum + t.budget_usd, 0)
  let number = 0
  const list = (steps: BookingStep[]) => (
    <ol className="steps">
      {steps.map((step) => (
        <Step
          key={step.id}
          step={step}
          number={step.url ? ++number : null}
          who={solo || step.traveler ? [] : whoIsIn(step.who, travelers.length)}
        />
      ))}
    </ol>
  )

  return (
    <section className="finish">
      <h1>Your trip is ready to book</h1>
      <p className="lede">
        Each link opens the provider with your details already filled in wherever the site accepts them.
        You book and pay there yourself. Tripwright never does.
      </p>

      {travelers.map((t) => {
        const steps = booking.filter((step) => step.traveler === t.id)
        if (steps.length === 0) return null
        return (
          <section key={t.id} className="group">
            <h2>{solo ? 'Your bookings' : `${t.name}'s bookings`}</h2>
            {list(steps)}
          </section>
        )
      })}
      {SHARED.map(([category, heading]) => {
        const steps = booking.filter((step) => step.category === category)
        if (steps.length === 0) return null
        return (
          <section key={category} className={`group cat-${category}`}>
            <h2><i className="dot" />{heading}</h2>
            {list(steps)}
          </section>
        )
      })}

      <footer className="finish-total">
        <div>
          <strong>{money(total)}</strong> to book
          <span className="muted"> of {solo ? 'your' : "the group's combined"} {money(budget)} budget</span>
        </div>
        <button onClick={onBack}>Back to review</button>
      </footer>
    </section>
  )
}

/** `who` names the people a shared step is for; empty where the section already says. */
function Step({ step, number, who }: { step: BookingStep; number: number | null; who: string[] }) {
  return (
    <li className={`step cat-${step.category}${step.url ? '' : ' nothing'}`}>
      <span className="number">{number ?? '✓'}</span>
      <div className="what">
        <h3>{step.title}</h3>
        {step.when && <p className="when">{step.when}</p>}
        <Chips label="For" items={who} />
        {step.filled.length > 0 && (
          <ul className="filled" aria-label="Already filled in">
            {step.filled.map((detail) => <li key={detail}>✓ {detail}</li>)}
          </ul>
        )}
        {step.todo && <p className="todo">{step.todo}</p>}
      </div>
      <div className="go">
        {step.price_usd > 0 && <span className="price">{money(step.price_usd)}</span>}
        {step.url && (
          <a className="open" href={safeHref(step.url)} target="_blank" rel="noreferrer">
            {LINK_LABEL[step.link]} ↗
            {step.provider && <small>{step.provider}</small>}
          </a>
        )}
      </div>
    </li>
  )
}
