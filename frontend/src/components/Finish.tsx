import { money, safeHref, whoIsIn } from '../format'
import type { BookingStep, Category, Traveler, TripView } from '../types'
import { Chips } from './Chips'

/** What the group books together; each traveler's own flight, stays and transport come first. */
const SHARED: [Category, string][] = [
  ['attractions', 'Tickets'],
]

const LINK_LABEL: Record<BookingStep['link'], string> = {
  filled: 'Open with details filled in',
  booking: 'Open the booking page',
  info: 'See how to buy',
}

interface Props {
  view: TripView
  you: Traveler
}

/** The hand-off: everything to book, in order, each with a link that already carries the trip's details.
 *  Each traveler sees their own flight and stays, and the bookings the group shares. */
export function Finish({ view, you }: Props) {
  const { booking, state } = view
  const { travelers } = state
  const solo = travelers.length < 2
  const mine = booking.filter((step) => step.traveler === you.id)
  // Shared tickets are priced for everyone going; the budget has each traveler's own share.
  const total = state.budgets[you.id]?.spent_usd ?? booking.reduce((sum, step) => sum + step.price_usd, 0)
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

      {mine.length > 0 && (
        <section className="group">
          <h2>Your bookings</h2>
          {list(mine)}
        </section>
      )}
      {SHARED.map(([category, heading]) => {
        // Each traveler's own flight, rooms and transport are listed above, under "Your bookings".
        const steps = booking.filter((step) => step.category === category && !step.traveler)
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
          <strong>{money(total)}</strong> {solo ? 'to book' : 'is your share'}
          <span className="muted"> of your {money(you.budget_usd)} budget</span>
        </div>
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
