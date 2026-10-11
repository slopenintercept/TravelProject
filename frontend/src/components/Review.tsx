import { useState } from 'react'
import { money, safeHref, whoIsIn } from '../format'
import {
  CATEGORIES, type Card, type Category, type DecisionAction, type Flag, type Traveler, type TripView, type Violation,
} from '../types'
import { Chips } from './Chips'

type Decide = (action: DecisionAction, card: string, optionId?: string) => void

/** `state.flags` is keyed by agent name, not by category. Flights have one agent per traveler
 *  ("flight:<traveler>"), so each traveler sees their own flight flag. */
const AGENT: Record<Category, string> = {
  flights: 'flight', lodging: 'lodging', attractions: 'attractions', transport: 'transport',
}

function FlagBadge({ flag }: { flag: Flag }) {
  return (
    <p className={`flag flag-${flag.kind}`}>
      <strong>{flag.kind}</strong> {flag.reason}
    </p>
  )
}

export function Violations({ violations }: { violations: Violation[] }) {
  if (violations.length === 0) return null
  return (
    <div className="banner error" role="alert">
      <div>
        <strong>{violations.length === 1 ? '1 conflict to resolve' : `${violations.length} conflicts to resolve`}</strong>
        <ul>
          {violations.map((v, i) => (
            <li key={i} className={`severity-${v.severity}`}>{v.message}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/** The "most travelers here pick..." explanation that heads the lodging and transport groups. */
function DefaultCard({ card, busy, onDecision }: { card: Card; busy: boolean; onDecision: Decide }) {
  return (
    <article className="card default">
      <h3>{card.title}</h3>
      {card.detail && <p className="detail">{card.detail}</p>}
      {card.reasoning && <p className="reasoning">{card.reasoning}</p>}
      {card.switch_label && (
        <footer>
          <button disabled={busy} onClick={() => onDecision('switch', card.id)}>{card.switch_label}</button>
        </footer>
      )}
    </article>
  )
}

/** `groupSize` is how many travelers are on the trip. */
function ItemCard({ card, groupSize, busy, onDecision }: { card: Card; groupSize: number; busy: boolean; onDecision: Decide }) {
  const [swapping, setSwapping] = useState(false)
  const removed = card.status === 'removed'
  // Flights and stays can only be swapped; must-haves stay on the trip.
  const removable = !card.must_have && /^(attraction|leg):/.test(card.id)

  return (
    <article className={`card card-${card.status}`}>
      <header>
        <h3>{card.title}</h3>
        <span className="price">{card.price_usd > 0 ? money(card.price_usd) : 'Free'}</span>
      </header>
      <div className="badges">
        {removed && <span className={`pill card-status-${card.status}`}>{card.status}</span>}
        {card.must_have && <span className="pill must-have">must-have</span>}
        {card.flag && (
          <span className={`pill status-${card.flag.kind}`} title={card.flag.reason}>
            {card.flag.kind === 'fallback' ? 'saved result' : 'pending'}
          </span>
        )}
      </div>
      {groupSize > 1 && (
        <div className="who">
          <Chips label="Needs it" items={card.need_by} />
          <Chips label="Wants it" items={card.want_by} />
          <Chips label="Skipping" items={card.skip_by} />
          <Chips label="Going" items={whoIsIn(card.going, groupSize)} />
        </div>
      )}
      {card.detail && <p className="detail">{card.detail}</p>}
      {card.reasoning && <p className="reasoning">{card.reasoning}</p>}
      {card.booking_url && (
        <a className="booking" href={safeHref(card.booking_url)} target="_blank" rel="noreferrer">
          Finish booking on the provider's site ↗
        </a>
      )}

      <footer>
        {/* No Approve button: approving didn't change anything, so cards only offer what does. */}
        {!removed && card.alternatives.length > 0 && (
          <button disabled={busy} onClick={() => setSwapping(!swapping)}>{swapping ? 'Cancel swap' : 'Swap'}</button>
        )}
        {removable && (
          <button disabled={busy} onClick={() => onDecision(removed ? 'restore' : 'remove', card.id)}>
            {removed ? 'Restore' : 'Remove'}
          </button>
        )}
      </footer>

      {swapping && !removed && (
        <ul className="alternatives">
          {card.alternatives.map((option) => (
            <li key={option.id}>
              <div>
                <strong>{option.title}</strong>
                {option.detail && <p>{option.detail}</p>}
              </div>
              <span className="price">{money(option.price_usd)}</span>
              <button
                disabled={busy}
                onClick={() => {
                  setSwapping(false)
                  onDecision('swap', card.id, option.id)
                }}
              >
                Choose
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}

interface Props {
  view: TripView
  /** Who is looking: they decide on their own flight, stays and budget, and with everyone on what is shared. */
  you: Traveler
  busy: boolean
  onDecision: Decide
  onApplyBudget: (travelerId: string) => void
}

export function Review({ view, you, busy, onDecision, onApplyBudget }: Props) {
  const { state, cards } = view
  const { travelers } = state
  const proposal = state.budget_proposals[you.id]
  const item = (card: Card) => (
    <ItemCard key={card.id} card={card} groupSize={travelers.length} busy={busy} onDecision={onDecision} />
  )

  return (
    <div className="review">
      {proposal && (
        <div className="banner warn">
          <div>
            <strong>
              {proposal.swaps.length === 0
                ? "You're over budget, and no swap would bring it down."
                : `You're over budget. These swaps bring your total to ${money(proposal.new_total_usd)}${proposal.fits ? ', within your budget.' : ', which is still over.'}`}
            </strong>
            <ul>
              {proposal.swaps.map((swap, i) => (
                <li key={i}>{swap.title} <span className="saves">saves {money(swap.saves_usd)}</span></li>
              ))}
            </ul>
          </div>
          {proposal.swaps.length > 0 && (
            <button className="primary" disabled={busy} onClick={() => onApplyBudget(you.id)}>Apply swaps</button>
          )}
        </div>
      )}

      {CATEGORIES.map((category) => {
        const group = cards.filter((card) => card.category === category)
        // Flights and stays are each traveler's own: everyone sees only theirs.
        const items = group.filter((card) => card.kind !== 'default' && (!card.traveler || card.traveler === you.id))
        // The reason is shown once per group; each affected card carries a short pill.
        const flag = category === 'flights' ? state.flags[`flight:${you.id}`] : state.flags[AGENT[category]]
        return (
          <section key={category} className={`group cat-${category}`}>
            <h2><i className="dot" />{category}</h2>
            {flag && <FlagBadge flag={flag} />}
            {group.length === 0 && <p className="muted">Nothing to review here yet.</p>}
            <div className="cards">
              {group.filter((card) => card.kind === 'default').map((card) => (
                <DefaultCard key={card.id} card={card} busy={busy} onDecision={onDecision} />
              ))}
              {items.map(item)}
              {category === 'transport' && !you.legs.some((leg) => leg.kind === 'rental_car' && leg.included) && (
                <button className="add" disabled={busy} onClick={() => onDecision('switch', `transport:${you.id}`)}>
                  Add a rental car
                </button>
              )}
            </div>
          </section>
        )
      })}
    </div>
  )
}
