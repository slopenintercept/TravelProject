import { money, safeHref, whoIsIn } from '../format'
import type { BookingStep, Category, TestCard, Traveler, TripView } from '../types'
import { Board } from './Board'
import { Chips } from './Chips'
import { Budget, Days } from './Days'
import { Pay } from './Pay'

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
  busy: boolean
  onApprove: (card: TestCard) => void
  onBackOut: () => void
}

/** The hand-off: the group pays together, then everything to book, in order, each with a link that already
 *  carries the trip's details. Each traveler sees their own flight and stays, and the bookings the group shares.
 *  The final days stay beside it. */
export function Finish({ view, you, busy, onApprove, onBackOut }: Props) {
  const { booking, state } = view
  const { travelers } = state
  const solo = travelers.length < 2
  const mine = booking.filter((step) => step.traveler === you.id)
  const budget = state.budgets[you.id]
  // Shared tickets are priced for everyone going; the budget has each traveler's own share.
  const total = budget?.spent_usd ?? booking.reduce((sum, step) => sum + step.price_usd, 0)
  let number = 0
  const list = (steps: BookingStep[]) => steps.map((step) => (
    <Step
      key={step.id}
      step={step}
      number={step.url ? ++number : null}
      who={solo || step.traveler ? [] : whoIsIn(step.who, travelers.length)}
    />
  ))

  return (
    <>
      <main className="feed">
        <div className="hd top"><h1 className="display h-40">Your trip is ready to book</h1></div>
        <p className="say">
          Each link opens the provider with your details already filled in wherever the site accepts them.
          You book there yourself.
        </p>

        <Pay state={state} you={you} busy={busy} onApprove={onApprove} onBackOut={onBackOut} />

        {mine.length > 0 && (
          <section>
            <div className="hd"><h2>Your bookings</h2></div>
            {list(mine)}
          </section>
        )}
        {SHARED.map(([category, heading]) => {
          // Each traveler's own flight, rooms and transport are listed above, under "Your bookings".
          const steps = booking.filter((step) => step.category === category && !step.traveler)
          if (steps.length === 0) return null
          return (
            <section key={category}>
              <div className="hd"><h2>{heading}</h2></div>
              {list(steps)}
            </section>
          )
        })}

        <p className="lede">
          <b>{money(total)}</b> {solo ? 'to book' : 'is your share'} of your {money(you.budget_usd)} budget.
        </p>
      </main>

      <Board plan="Your days">
        {budget && <Budget budget={budget} />}
        <Days state={state} you={you} />
      </Board>
    </>
  )
}

/** `who` names the people a shared step is for; empty where the section already says. */
function Step({ step, number, who }: { step: BookingStep; number: number | null; who: string[] }) {
  return (
    <article className={step.url ? 'card step' : 'card step nothing'}>
      <div className="top">
        <span className="num">{number ?? '✓'}</span>
        <div>
          <h3>{step.title}</h3>
          {step.when && <p className="when">{step.when}</p>}
        </div>
        {step.price_usd > 0 && <span className="n">{money(step.price_usd)}</span>}
      </div>
      <Chips label="For" items={who} />
      <Chips label="Already filled in" items={step.filled} />
      {step.todo && <p className="todo">{step.todo}</p>}
      {step.url && (
        <div className="go">
          <a className="pill sm solid" href={safeHref(step.url)} target="_blank" rel="noreferrer">
            {LINK_LABEL[step.link]} ↗{step.provider && <small>{step.provider}</small>}
          </a>
        </div>
      )}
    </article>
  )
}
