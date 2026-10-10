import { Fragment, useState } from 'react'
import { money, safeHref, whoIsIn } from '../format'
import { CATEGORIES, type Card, type Category, type DecisionAction, type Flag, type TripView, type Violation } from '../types'
import { Chips } from './Chips'

type Decide = (action: DecisionAction, card: string, optionId?: string) => void

/** `state.flags` is keyed by agent name, not by category. Flights have one agent per traveler
 *  ("flight:<traveler>"), so those flags are shown under each traveler. */
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
        <span className={`pill card-status-${card.status}`}>{card.status}</span>
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
        {!removed && (
          <button className="primary" disabled={busy || card.status === 'approved'} onClick={() => onDecision('approve', card.id)}>
            {card.status === 'approved' ? 'Approved' : 'Approve'}
          </button>
        )}
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
  busy: boolean
  onDecision: Decide
  onApplyBudget: (travelerId: string) => void
}

export function Review({ view, busy, onDecision, onApplyBudget }: Props) {
  const { state, cards } = view
  const { travelers } = state
  const solo = travelers.length < 2
  const item = (card: Card) => (
    <ItemCard key={card.id} card={card} groupSize={travelers.length} busy={busy} onDecision={onDecision} />
  )

  return (
    <div className="review">
      {travelers.map((t) => {
        const proposal = state.budget_proposals[t.id]
        if (!proposal) return null
        const over = solo ? 'Over budget' : `${t.name} is over budget`
        return (
          <div key={t.id} className="banner warn">
            <div>
              <strong>
                {proposal.swaps.length === 0
                  ? `${over}, and no swap would bring it down.`
                  : `${over}. These swaps bring ${solo ? 'the trip' : `${t.name}'s total`} to ${money(proposal.new_total_usd)}${proposal.fits ? `, within ${solo ? 'your' : 'their'} budget.` : ', which is still over.'}`}
              </strong>
              <ul>
                {proposal.swaps.map((swap, i) => (
                  <li key={i}>{swap.title} <span className="saves">saves {money(swap.saves_usd)}</span></li>
                ))}
              </ul>
            </div>
            {proposal.swaps.length > 0 && (
              <button className="primary" disabled={busy} onClick={() => onApplyBudget(t.id)}>Apply swaps</button>
            )}
          </div>
        )
      })}

      {CATEGORIES.map((category) => {
        const group = cards.filter((card) => card.category === category)
        const items = group.filter((card) => card.kind !== 'default')
        // The reason is shown once per group; each affected card carries a short pill.
        const flag = state.flags[AGENT[category]]
        return (
          <section key={category} className={`group cat-${category}`}>
            <h2><i className="dot" />{category}</h2>
            {flag && <FlagBadge flag={flag} />}
            {group.length === 0 && <p className="muted">Nothing to review here yet.</p>}
            <div className="cards">
              {group.filter((card) => card.kind === 'default').map((card) => (
                <DefaultCard key={card.id} card={card} busy={busy} onDecision={onDecision} />
              ))}
              {category !== 'attractions'
                ? travelers.map((t) => {
                    const theirs = items.filter((card) => card.traveler === t.id)
                    const theirFlag = category === 'flights' ? state.flags[`flight:${t.id}`] : undefined
                    if (theirs.length === 0 && !theirFlag) return null
                    return (
                      <Fragment key={t.id}>
                        {!solo && <h3>{t.name}</h3>}
                        {theirFlag && <FlagBadge flag={theirFlag} />}
                        {theirs.map(item)}
                        {category === 'transport' && !t.legs.some((leg) => leg.kind === 'rental_car' && leg.included) && (
                          <button className="add" disabled={busy} onClick={() => onDecision('switch', `transport:${t.id}`)}>
                            Add a rental car{solo ? '' : ` for ${t.name}`}
                          </button>
                        )}
                      </Fragment>
                    )
                  })
                : items.map(item)}
            </div>
          </section>
        )
      })}
    </div>
  )
}
