import { Fragment, useRef, useState } from 'react'
import { capitalize, clock, count, daysBetween, inWords, money, monthDay, safeHref, weekday, whoIsIn } from '../format'
import type {
  Alternative, Attraction, Card, DecisionAction, Flag, ItineraryItem, Traveler, TripState, TripView,
} from '../types'
import { AgentTag } from './Agents'
import { Board } from './Board'
import { Chips } from './Chips'
import { Budget, Days } from './Days'

type Decide = (action: DecisionAction, card: string, optionId?: string) => Promise<unknown>

/** "Delta: Kansas City to Haneda" is the airline, then the route; "Tokyo: the b asakusa" the city, then the room. */
function split(title: string): [string, string] {
  const at = title.indexOf(': ')
  return at > 0 ? [title.slice(0, at), title.slice(at + 2)] : ['', title]
}

const sameCity = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()
/** Monday is 0 in the trip's data, Sunday is 0 in the browser. */
const closedOn = (place: Attraction, day: string) => place.closed_weekdays.includes((new Date(`${day}T00:00:00`).getDay() + 6) % 7)
/** A place takes another activity's day, so it can only replace one in its own city on a day it is open. */
const canReplace = (place: Attraction, item: ItineraryItem) => sameCity(item.city, place.city) && !closedOn(place, item.day)
const listed = new Intl.ListFormat('en', { style: 'long', type: 'conjunction' })
const when = (item: ItineraryItem) => `${weekday(item.day)} ${monthDay(item.day)} · ${clock(item.start)}–${clock(item.end)}`

function FlagLine({ flag }: { flag: Flag }) {
  return <p className="flagline"><b>{flag.kind === 'fallback' ? 'Saved result.' : 'Pending.'}</b> {flag.reason}</p>
}

function Facts({ detail }: { detail: string }) {
  if (!detail) return null
  return <div className="facts">{detail.split(' · ').map((fact, i) => <span key={i} className="chip">{fact}</span>)}</div>
}

function Approval({ approved, label, busy, onApprove }: { approved: boolean; label: string; busy: boolean; onApprove: () => void }) {
  return approved
    ? <span className="approved"><i className="st" />Approved</span>
    : <button className="pill sm solid" disabled={busy} onClick={onApprove}>{label}</button>
}

/** The other options for a flight, a room or a leg, under the one they would replace. */
function Options({ options, note, busy, onChoose }: { options: Alternative[]; note?: string; busy: boolean; onChoose: (id: string) => void }) {
  return (
    <>
      {note && <p className="line sub small">{note}</p>}
      {options.map((option) => (
        <div key={option.id} className="line sub">
          <div><b>{option.title}</b>{option.detail && <small>{option.detail}</small>}</div>
          <span className="n">{money(option.price_usd)}</span>
          <button className="pill sm" disabled={busy} onClick={() => onChoose(option.id)}>Choose</button>
        </div>
      ))}
    </>
  )
}

interface GiveWayProps {
  place: Attraction
  state: TripState
  busy: boolean
  onPick: (itemId: string) => void
}

/** Swapping a place in: it takes another activity's slot, so the traveler picks which one gives way. */
function GiveWay({ place, state, busy, onPick }: GiveWayProps) {
  const { travelers } = state
  const needed = new Set(state.attractions.filter((a) => a.must_have).map((a) => a.id))
  const going = (ids: string[]) =>
    whoIsIn(travelers.filter((t) => ids.includes(t.id)).map((t) => t.name), travelers.length).join(', ')
  const shown = state.itinerary
    .filter((i) => i.kind === 'attraction' && canReplace(place, i))
    .sort((a, b) => (a.day + a.start).localeCompare(b.day + b.start))

  return (
    <div className="lines">
      {shown.length > 0 && <p className="ask">Which activity should give way? {place.name} takes its day, and that one comes off the trip.</p>}
      {shown.map((item) => (
        <div key={item.id} className="line">
          <div>
            <b>{item.title}</b>
            <small>
              {when(item)}{travelers.length > 1 && ` · ${going(item.travelers)}`}
              {item.ref_id && needed.has(item.ref_id) && ' · a must-see'}
            </small>
          </div>
          <button className="pill sm" disabled={busy} onClick={() => onPick(item.id)}>Replace</button>
        </div>
      ))}
      {shown.length === 0 && (
        <p className="line small">Nothing on your days is in {place.city} on a day {place.name} is open, so there is nothing it can replace.</p>
      )}
    </div>
  )
}

interface MissingProps extends GiveWayProps {
  whose: string
  reason: string
  onDrop: () => void
}

/** A must-see that is not on the days: swap it in for something, or drop it. */
function Missing({ place, whose, reason, state, busy, onPick, onDrop }: MissingProps) {
  const [open, setOpen] = useState(false)
  return (
    <article className="card need">
      <div className="head">
        <div>
          <h3>{place.name} didn't fit</h3>
          <p>{whose}. {capitalize(reason)}.</p>
        </div>
        <div className="acts">
          <button className="pill sm solid" aria-expanded={open} disabled={busy} onClick={() => setOpen(!open)}>
            {open ? 'Cancel' : 'Swap it in'}
          </button>
          <button className="pill sm" disabled={busy} onClick={onDrop}>Drop</button>
        </div>
      </div>
      {open && <GiveWay place={place} state={state} busy={busy} onPick={onPick} />}
    </article>
  )
}

function Flight({ card, flag, busy, onDecision }: { card?: Card; flag?: Flag; busy: boolean; onDecision: Decide }) {
  const [swapping, setSwapping] = useState(false)
  if (!card) {
    return (
      <article className="card">
        <p className="small">The flight agent didn't find options for you, so your flight is still to book.</p>
        {flag && <FlagLine flag={flag} />}
      </article>
    )
  }
  const [airline, route] = split(card.title)
  const others = card.alternatives.length
  return (
    <article className="card choice">
      <div className="top">
        <div><span className="cap">{airline}</span><h3>{route}</h3></div>
        <div className="price">{money(card.price_usd)}</div>
      </div>
      <Facts detail={card.detail} />
      {card.flag && <FlagLine flag={card.flag} />}
      {card.reasoning && <p className="why"><b>Why this pick.</b> {card.reasoning}</p>}
      <div className="go flush">
        <Approval approved={card.status === 'approved'} label="Approve" busy={busy} onApprove={() => onDecision('approve', card.id)} />
        {others > 0 && (
          <button className="pill sm" aria-expanded={swapping} disabled={busy} onClick={() => setSwapping(!swapping)}>
            {swapping ? 'Cancel swap' : `Swap · ${count(others, 'other')}`}
          </button>
        )}
        <span className="grow" />
        {card.booking_url && (
          <a className="pill sm" href={safeHref(card.booking_url)} target="_blank" rel="noreferrer">Book on provider's site ↗</a>
        )}
      </div>
      {swapping && (
        <div className="lines">
          <Options options={card.alternatives} busy={busy} onChoose={(id) => { setSwapping(false); onDecision('swap', card.id, id) }} />
        </div>
      )}
    </article>
  )
}

interface GroupProps {
  cards: Card[]
  you: Traveler
  flag?: Flag
  busy: boolean
  onDecision: Decide
}

/** Every room on the trip in one card: each can be swapped, and all are approved together. */
function Stays({ cards, you, flag, busy, onDecision }: GroupProps) {
  const [swapping, setSwapping] = useState<string | null>(null)
  const stays = cards.filter((c) => c.category === 'lodging' && c.kind === 'item' && c.traveler === you.id)
  const common = cards.find((c) => c.id === 'lodging')
  if (stays.length === 0) {
    return <article className="card"><p className="small">No rooms to review yet.</p>{flag && <FlagLine flag={flag} />}</article>
  }
  const waiting = stays.filter((c) => c.status !== 'approved')
  const nights = (you.lodging?.stays ?? []).reduce((sum, s) => sum + daysBetween(s.check_in, s.check_out).length - 1, 0)

  async function approveAll() {
    for (const card of waiting) await onDecision('approve', card.id)
  }

  return (
    <article className="card choice">
      <div className="top">
        <div>
          {common && <span className="cap">{common.title.replace(':', '')}</span>}
          <h3>{capitalize(inWords(stays.length))} {stays.length === 1 ? 'stay' : 'stays'}, {inWords(nights)} {nights === 1 ? 'night' : 'nights'}</h3>
        </div>
        <div className="price">{money(stays.reduce((sum, c) => sum + c.price_usd, 0))}</div>
      </div>
      {flag && <FlagLine flag={flag} />}
      <div className="lines">
        {stays.map((card) => {
          const [city, room] = split(card.title)
          const open = swapping === card.id
          return (
            <Fragment key={card.id}>
              <div className="line">
                <div><b>{room}</b><small>{[city, card.detail].filter(Boolean).join(' · ')}</small></div>
                <span className="n">{money(card.price_usd)}</span>
                {card.alternatives.length > 0 && (
                  <button className="pill sm" aria-expanded={open} disabled={busy} onClick={() => setSwapping(open ? null : card.id)}>
                    {open ? 'Cancel' : 'Swap'}
                  </button>
                )}
              </div>
              {open && (
                <Options
                  options={card.alternatives}
                  note={card.reasoning}
                  busy={busy}
                  onChoose={(id) => { setSwapping(null); onDecision('swap', card.id, id) }}
                />
              )}
            </Fragment>
          )
        })}
      </div>
      {common?.reasoning && <p className="why"><b>Why this pick.</b> {common.reasoning}</p>}
      <div className="go flush">
        <Approval
          approved={waiting.length === 0}
          label={stays.length === 1 ? 'Approve this stay' : waiting.length < stays.length ? 'Approve the rest' : `Approve all ${inWords(stays.length)}`}
          busy={busy}
          onApprove={approveAll}
        />
        {common?.switch_label && (
          <button className="pill sm" disabled={busy} onClick={() => onDecision('switch', common.id)}>{common.switch_label}</button>
        )}
      </div>
    </article>
  )
}

/** The traveler's own transport legs: each can be swapped for another way to make the trip, or taken off. */
function GettingAround({ cards, you, flag, busy, onDecision }: GroupProps) {
  const [swapping, setSwapping] = useState<string | null>(null)
  const legs = cards.filter((c) => c.category === 'transport' && c.kind === 'item' && c.traveler === you.id)
  const common = cards.find((c) => c.id === 'transport')
  const kept = legs.filter((c) => c.status !== 'removed')
  const hasCar = you.legs.some((leg) => leg.kind === 'rental_car' && leg.included)
  const addCar = !hasCar && (
    <div className="go flush">
      <button className="pill sm" disabled={busy} onClick={() => onDecision('switch', `transport:${you.id}`)}>Add a rental car</button>
    </div>
  )
  if (legs.length === 0 && !common) {
    return (
      <>
        <div className="hd"><h2>Getting around</h2><AgentTag agent="transport" /></div>
        <article className="card">
          <p className="small">The transport agent didn't find how to get around, so your legs are still to plan.</p>
          {flag && <FlagLine flag={flag} />}
          {addCar}
        </article>
      </>
    )
  }

  return (
    <>
      <div className="hd"><h2>Getting around</h2><AgentTag agent="transport" /></div>
      <article className="card choice">
        <div className="top">
          <div>
            {common && <span className="cap">{common.title.replace(':', '')}</span>}
            <h3>{capitalize(inWords(kept.length))} {kept.length === 1 ? 'leg' : 'legs'}</h3>
          </div>
          <div className="price">{money(kept.reduce((sum, c) => sum + c.price_usd, 0))}</div>
        </div>
        {flag && <FlagLine flag={flag} />}
        <div className="lines">
          {legs.map((card) => {
            const open = swapping === card.id
            const removed = card.status === 'removed'
            return (
              <Fragment key={card.id}>
                <div className={removed ? 'line off' : 'line'}>
                  <div><b>{card.title}</b><small>{[card.detail, card.reasoning].filter(Boolean).join(' · ')}</small></div>
                  <span className="n">{card.price_usd > 0 ? money(card.price_usd) : 'Free'}</span>
                  <span className="acts">
                    {!removed && card.alternatives.length > 0 && (
                      <button className="pill sm" aria-expanded={open} disabled={busy} onClick={() => setSwapping(open ? null : card.id)}>
                        {open ? 'Cancel' : 'Swap'}
                      </button>
                    )}
                    {/* The trips between cities stay: the days are planned around them. */}
                    {!card.must_have && (
                      <button className="pill sm" disabled={busy} onClick={() => onDecision(removed ? 'restore' : 'remove', card.id)}>
                        {removed ? 'Restore' : 'Remove'}
                      </button>
                    )}
                  </span>
                </div>
                {open && !removed && (
                  <Options options={card.alternatives} busy={busy} onChoose={(id) => { setSwapping(null); onDecision('swap', card.id, id) }} />
                )}
              </Fragment>
            )
          })}
        </div>
        {common?.reasoning && <p className="why"><b>Why this pick.</b> {common.reasoning}</p>}
        {addCar}
      </article>
    </>
  )
}

interface Props {
  view: TripView
  /** Who is looking: they decide on their own flight, stays and budget, and with everyone on what is shared. */
  you: Traveler
  busy: boolean
  onDecision: Decide
  onApplyBudget: (travelerId: string) => void
  onMove: (itemId: string, day: string) => void
  onSwap: (itemId: string, attractionId: string) => void
  onFinish: () => void
}

/** Review: the feed asks for each decision, and the days stay beside it. Clicking an activity on the calendar
 *  brings it to the top of the feed. */
export function Review({ view, you, busy, onDecision, onApplyBudget, onMove, onSwap, onFinish }: Props) {
  const { state, cards } = view
  const { travelers } = state
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [swapping, setSwapping] = useState(false) // the selected activity's "swap for" list
  const [swapIn, setSwapIn] = useState<string | null>(null) // the left-off place being swapped in
  const feed = useRef<HTMLElement>(null)
  const solo = travelers.length < 2
  const named = (ids: string[]) => travelers.filter((t) => ids.includes(t.id)).map((t) => t.name)

  const onDays = new Set(state.itinerary.filter((i) => i.kind === 'attraction').map((i) => i.ref_id))
  const unscheduled = new Map(state.unscheduled.map((u) => [u.attraction_id, u]))
  // Must-sees the scheduler could not place: each needs a decision.
  const missing = state.attractions.filter((a) => a.must_have && a.included && !onDays.has(a.id))
  // Everything else that is off the days: places nobody needs that didn't fit, and places taken off the trip.
  const leftOff = state.attractions.filter((a) => !onDays.has(a.id) && !missing.includes(a))
  const problems = state.violations.filter((v) =>
    v.code !== 'OVER_BUDGET' && !(v.code === 'MUST_HAVE_MISSING' && missing.some((a) => v.message.includes(a.name))))
  const budget = state.budgets[you.id]
  const proposal = state.budget_proposals[you.id]
  const over = budget && budget.remaining_usd < 0
  const whyOff = (a: Attraction) => (a.included ? unscheduled.get(a.id)?.reason ?? 'not on your days' : 'taken off the trip')
  /** "Your must-see", "Sam's must-see", "A must-see for you and Sam" */
  function whoseMustSee(place: Attraction): string {
    const others = named(place.need_by.filter((id) => id !== you.id))
    const mine = place.need_by.includes(you.id)
    if (mine && others.length === 0) return 'Your must-see'
    if (!mine && others.length === 1) return `${others[0]}'s must-see`
    return others.length === 0 ? 'A must-see' : `A must-see for ${listed.format([...(mine ? ['you'] : []), ...others])}`
  }

  // The selection can disappear after a re-plan (a move or swap makes new items).
  const selected = state.itinerary.find((i) => i.id === selectedId && !i.locked)
  const selectedCard = selected && cards.find((c) => c.id === `attraction:${selected.ref_id}`)
  const selectedPlace = selected && state.attractions.find((a) => a.id === selected.ref_id)
  const issues = selected ? state.violations.filter((v) => v.item_ids.includes(selected.id)) : []
  // What could take the selected activity's slot: places off the days, in that day's city and open that day.
  const swappable = selected ? [...missing, ...leftOff].filter((a) => canReplace(a, selected)) : []

  function select(id: string | null) {
    setSelectedId(id === selectedId ? null : id)
    setSwapping(false)
    feed.current?.scrollTo({ top: 0 })
  }
  function swap(itemId: string, attractionId: string) {
    setSelectedId(null)
    setSwapIn(null)
    onSwap(itemId, attractionId)
  }

  return (
    <>
      <main className="feed" ref={feed}>
        {selected && (
          <section>
            <div className="hd"><h2>On your days</h2><AgentTag agent="attractions" /></div>
            <article className="card choice">
              <div className="top">
                <div>
                  <span className="cap">{when(selected)} · {selected.city}</span>
                  <h3>{selected.title}</h3>
                </div>
                <div className="price">{selected.cost_usd > 0 ? money(selectedCard?.price_usd ?? selected.cost_usd) : 'Free'}</div>
              </div>
              {!solo && <Chips label="Going" items={whoIsIn(named(selected.travelers), travelers.length)} />}
              {!solo && selectedCard && <Chips label="Needs it" items={selectedCard.need_by} />}
              {!solo && selectedCard && <Chips label="Wants it" items={selectedCard.want_by} />}
              {!solo && selectedCard && <Chips label="Skipping" items={selectedCard.skip_by} />}
              <Facts detail={selectedCard?.detail ?? ''} />
              {selectedCard?.flag && <FlagLine flag={selectedCard.flag} />}
              {issues.map((v) => <p key={v.message} className="flagline">{v.message}</p>)}
              {selectedCard?.note && <p className="why">{selectedCard.note}</p>}
              {selectedCard?.reasoning && <p className="why"><b>Why this pick.</b> {selectedCard.reasoning}</p>}
              <div className="go flush">
                {swappable.length > 0 && (
                  <button className="pill sm" aria-expanded={swapping} disabled={busy} onClick={() => setSwapping(!swapping)}>
                    {swapping ? 'Cancel swap' : 'Swap for…'}
                  </button>
                )}
                {selectedPlace && (selectedPlace.must_have
                  ? <span className="small">Someone needs this, so it stays.</span>
                  : (
                    <button className="pill sm" disabled={busy} onClick={() => { setSelectedId(null); onDecision('remove', `attraction:${selectedPlace.id}`) }}>
                      Take it off the trip
                    </button>
                  ))}
                <span className="grow" />
                {selectedCard?.booking_url && (
                  <a className="pill sm" href={safeHref(selectedCard.booking_url)} target="_blank" rel="noreferrer">Tickets ↗</a>
                )}
                <button className="textlink" onClick={() => setSelectedId(null)}>Close</button>
              </div>
              {swapping && (
                <div className="lines">
                  {swappable.map((a) => (
                    <div key={a.id} className="line sub">
                      <div><b>{a.name}</b><small>{a.city} · {capitalize(whyOff(a))}</small></div>
                      <button className="pill sm" disabled={busy} onClick={() => swap(selected.id, a.id)}>Choose</button>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </section>
        )}

        <section>
          <div className="hd"><h2>Needs you</h2><AgentTag agent="validate" /></div>
          {missing.length + problems.length === 0 && !over && <p className="small">Nothing needs you right now.</p>}
          {missing.map((place) => (
            <Missing
              key={place.id}
              place={place}
              whose={whoseMustSee(place)}
              reason={whyOff(place)}
              state={state}
              busy={busy}
              onPick={(itemId) => swap(itemId, place.id)}
              onDrop={() => onDecision('remove', `attraction:${place.id}`)}
            />
          ))}
          {problems.map((v) => (
            <article key={v.message} className="card need">
              <h3>{v.message}</h3>
              {v.item_ids.length > 0 && <p>It is outlined on your days. Drag it to another day, or click it to swap it or take it off.</p>}
            </article>
          ))}
          {over && (
            <article className="card need">
              <div className="head">
                <div>
                  <h3>Your plan is {money(-budget.remaining_usd)} over budget</h3>
                  <p>
                    {money(budget.spent_usd)} against {money(budget.total_usd)}
                    {proposal && proposal.swaps.length > 0
                      ? `. These swaps bring it to ${money(proposal.new_total_usd)}${proposal.fits ? ', within your budget.' : ', which is still over.'}`
                      : ', and no swap would bring it down.'}
                  </p>
                </div>
                {proposal && proposal.swaps.length > 0 && (
                  <div className="acts">
                    <button className="pill sm solid" disabled={busy} onClick={() => onApplyBudget(you.id)}>Apply swaps</button>
                  </div>
                )}
              </div>
              {proposal && proposal.swaps.length > 0 && (
                <ul className="swaps">
                  {proposal.swaps.map((s, i) => <li key={i}>{s.title} <b>saves {money(s.saves_usd)}</b></li>)}
                </ul>
              )}
            </article>
          )}
        </section>

        <section>
          <div className="hd"><h2>Your flight</h2><AgentTag agent={`flight:${you.id}`} /></div>
          <Flight card={cards.find((c) => c.id === `flight:${you.id}`)} flag={state.flags[`flight:${you.id}`]} busy={busy} onDecision={onDecision} />
        </section>

        <section>
          <div className="hd"><h2>Your stays</h2><AgentTag agent="lodging" /></div>
          <Stays cards={cards} you={you} flag={state.flags.lodging} busy={busy} onDecision={onDecision} />
        </section>

        <section>
          <GettingAround cards={cards} you={you} flag={state.flags.transport} busy={busy} onDecision={onDecision} />
        </section>

        {state.flags.attractions && (
          <section>
            <div className="hd"><h2>Things to do</h2><AgentTag agent="attractions" /></div>
            <article className="card">
              <FlagLine flag={state.flags.attractions} />
              {state.flags.attractions.kind === 'fallback' && <p className="small">The activities on your days come from this saved result.</p>}
            </article>
          </section>
        )}

        {leftOff.length > 0 && (
          <section>
            <div className="hd"><h2>Left off your days</h2><AgentTag agent="scheduler" /></div>
            <article className="card">
              <div className="lines flush">
                {leftOff.map((place) => {
                  const wanted = unscheduled.get(place.id)?.wanted_by ?? []
                  const open = swapIn === place.id
                  return (
                    <Fragment key={place.id}>
                      <div className="line">
                        <div>
                          <b>{place.name}</b>
                          <small>
                            {capitalize(whyOff(place))}
                            {!solo && wanted.length > 0 && ` · wanted by ${wanted.length === travelers.length ? 'everyone' : named(wanted).join(', ')}`}
                          </small>
                        </div>
                        {place.included ? (
                          <button className="pill sm" aria-expanded={open} disabled={busy} onClick={() => setSwapIn(open ? null : place.id)}>
                            {open ? 'Cancel' : 'Swap it in'}
                          </button>
                        ) : (
                          <button className="pill sm" disabled={busy} onClick={() => onDecision('restore', `attraction:${place.id}`)}>Put back</button>
                        )}
                      </div>
                      {open && <GiveWay place={place} state={state} busy={busy} onPick={(itemId) => swap(itemId, place.id)} />}
                    </Fragment>
                  )
                })}
              </div>
            </article>
          </section>
        )}
      </main>

      <Board plan="Your days">
        {budget && <Budget budget={budget} />}
        <Days
          state={state}
          you={you}
          busy={busy}
          onMove={(itemId, day) => { setSelectedId(null); onMove(itemId, day) }}
          onSelect={(item) => select(item.id)}
          selectedId={selected?.id}
          action={<button className="pill sm solid" disabled={busy} onClick={onFinish}>Finish →</button>}
        />
      </Board>
    </>
  )
}
