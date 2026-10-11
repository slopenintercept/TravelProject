import { useState } from 'react'
import { count, money } from '../format'
import type { Payment, TestCard, Traveler, TripState } from '../types'

/** The test cards a traveler can pick. The first two match the labels in payments.py. */
const CARDS: [TestCard, string][] = [
  ['visa', 'Visa ···· 4242'],
  ['mastercard', 'Mastercard ···· 4444'],
  ['declined', 'A card that declines'],
]

function dot(payment?: Payment): string {
  return payment?.status === 'captured' ? '' : payment?.status === 'held' ? 'review' : payment?.status === 'declined' ? 'bad' : 'idle'
}

function standing(payment?: Payment): string {
  switch (payment?.status) {
    case 'held': return `On hold · ${payment.card}`
    case 'captured': return `Paid · ${payment.card}`
    case 'declined': return `${payment.card} was declined`
    case 'released': return 'Hold released'
    default: return 'Has not approved yet'
  }
}

interface Props {
  state: TripState
  you: Traveler
  busy: boolean
  onApprove: (card: TestCard) => void
  onBackOut: () => void
}

/** Paying together: each traveler approves their own share on a test card. Approving places a hold; everyone
 *  is charged at once when the whole group is in, and if anyone backs out first every hold is released. */
export function Pay({ state, you, busy, onApprove, onBackOut }: Props) {
  const [card, setCard] = useState<TestCard>('visa')
  const { travelers } = state
  const payments = state.payments ?? {} // a server started before payments existed doesn't send them
  const solo = travelers.length < 2
  const reserved = (t: Traveler) => ['held', 'captured'].includes(payments[t.id]?.status)
  // A hold keeps the amount it was placed for; until then the share is the traveler's part of the plan.
  const share = (t: Traveler) => (reserved(t) ? payments[t.id].amount_usd : state.budgets[t.id]?.spent_usd ?? 0)
  const held = travelers.filter((t) => payments[t.id]?.status === 'held')
  const paid = travelers.every((t) => payments[t.id]?.status === 'captured')
  const total = travelers.reduce((sum, t) => sum + share(t), 0)

  return (
    <section>
      <div className="hd">
        <h2>{solo ? 'Pay for your trip' : 'Pay together'}</h2>
        {!solo && <span className="chip">{paid ? 'Everyone paid' : `${held.length} of ${travelers.length} approved`}</span>}
      </div>
      <article className="card pay">
        <p className="small">
          {solo
            ? 'Approving charges your card for the whole trip.'
            : 'Approving places a hold on your card for your share. Nobody is charged until everyone has approved, and if anyone backs out, every hold is released.'}
        </p>
        <ul className="shares">
          {travelers.map((t) => (
            <li key={t.id}>
              <i className={`st ${dot(payments[t.id])}`} />
              <div>
                <b>{t.name}{t.id === you.id && !solo && ' (you)'}</b>
                <span className="small">{standing(payments[t.id])}</span>
              </div>
              <span className="n">{money(share(t))}</span>
            </li>
          ))}
        </ul>

        {paid ? (
          <p className="say">Trip paid. {money(total)} charged across {count(travelers.length, 'card')}.</p>
        ) : reserved(you) ? (
          <div className="go flush">
            <p className="small grow">Your share is on hold. You are charged only when everyone has approved.</p>
            <button className="pill sm" disabled={busy} onClick={onBackOut}>Back out</button>
          </div>
        ) : (
          <>
            <div className="view" role="group" aria-label="Card to use">
              {CARDS.map(([id, label]) => (
                <button key={id} aria-pressed={card === id} onClick={() => setCard(id)}>{label}</button>
              ))}
            </div>
            <div className="go">
              <button className="pill solid wide" disabled={busy || share(you) <= 0} onClick={() => onApprove(card)}>
                Approve my share: {solo ? 'pay' : 'hold'} {money(share(you))}
              </button>
              {held.length > 0 && <button className="pill" disabled={busy} onClick={onBackOut}>Back out</button>}
            </div>
          </>
        )}
        <p className="small fine">
          {Object.values(payments).some((p) => p.ref) && 'Runs on Stripe test mode. '}Test cards only. No money moves.
        </p>
      </article>
    </section>
  )
}
