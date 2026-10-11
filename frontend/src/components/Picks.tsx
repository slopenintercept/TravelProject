import { useState, type FormEvent } from 'react'
import type { Idea, Picks as Marks, Traveler, TripState } from '../types'
import { Chips } from './Chips'

type Mark = keyof Marks

const MARKS: [Mark, string][] = [
  ['need', 'Must do'],
  ['want', 'Interested'],
  ['skip', 'Not for me'],
]
const LABEL = Object.fromEntries(MARKS) as Record<Mark, string>
const STILL_WORKING = ['working', 'under_review', 'sent_back']

const key = (name: string) => name.toLowerCase().split(/\s+/).join(' ')

/** A traveler's mark on a place, if any. */
function markOf(t: Traveler, idea: Idea): Mark | null {
  return MARKS.map(([mark]) => mark).find((mark) => t[mark].some((name) => key(name) === key(idea.name))) ?? null
}

interface Props {
  state: TripState
  you: Traveler
  busy: boolean
  /** Resolves to whether the picks were saved. */
  onSave: (picks: Marks) => Promise<boolean>
  onAdd: (name: string, city: string) => Promise<boolean>
  /** Keep these marks and ask the agents for more places like them. */
  onMore: (picks: Marks) => Promise<boolean>
}

/** "What sounds good?": everyone marks the same list of places the agents found, and can add their own. */
export function Picks({ state, you, busy, onSave, onAdd, onMore }: Props) {
  const [marks, setMarks] = useState<Record<string, Mark>>(() =>
    Object.fromEntries(state.ideas.flatMap((idea) => {
      const mark = markOf(you, idea)
      return mark ? [[idea.id, mark]] : []
    })),
  )
  const [place, setPlace] = useState({ name: '', city: '' })
  const status = state.agents.ideas?.status
  const searching = !!status && STILL_WORKING.includes(status)
  const more = state.agents[`more_ideas:${you.id}`]?.status
  const findingMore = !!more && STILL_WORKING.includes(more)
  const group = state.travelers.length > 1
  const marked = Object.keys(marks).length > 0

  /** Who on the trip marked this place `value`: you by your marks on this screen, the others by their saved ones. */
  function who(idea: Idea, value: Mark): string[] {
    return state.travelers
      .filter((t) => (t.id === you.id ? marks[idea.id] : markOf(t, idea)) === value)
      .map((t) => (t.id === you.id ? 'You' : t.name))
  }

  // Categories in the order the agents listed them; places people added come last.
  const groups = new Map<string, Idea[]>()
  for (const idea of state.ideas) groups.set(idea.category || 'Other', [...(groups.get(idea.category || 'Other') ?? []), idea])

  function mark(idea: Idea, value: Mark) {
    setMarks(({ [idea.id]: current, ...rest }) => (current === value ? rest : { ...rest, [idea.id]: value }))
  }

  function picks(): Marks {
    const chosen: Marks = { need: [], want: [], skip: [] }
    for (const idea of state.ideas) {
      if (marks[idea.id]) chosen[marks[idea.id]].push(idea.name)
    }
    return chosen
  }

  async function add(e: FormEvent) {
    e.preventDefault()
    if (await onAdd(place.name.trim(), place.city.trim())) setPlace({ name: '', city: '' })
  }

  return (
    <section className="picks">
      <h1>What sounds good?</h1>
      <p className="lede">
        {searching
          ? `Agents are finding places to see and things to do in ${state.request.destination}…`
          : state.ideas.length > 0
            ? 'Mark what you must do, what interests you, and what is not for you. Leave the rest blank. The agents plan your days and the group\'s from these.'
            : "The agents couldn't suggest places for this trip. Add the places you want below."}
      </p>
      {searching && <p className="working"><i className="spinner" />Researching…</p>}

      {[...groups].map(([category, ideas]) => (
        <section key={category} className="idea-group">
          <h2>{category}</h2>
          <ul className="ideas">
            {ideas.map((idea) => (
              <li key={idea.id} className="idea panel">
                <div className="what">
                  <h3>
                    {idea.name}
                    {idea.suggested_for && (
                      <span className="pill new">
                        {idea.suggested_for === you.id
                          ? 'New · suggested for you'
                          : `Suggested for ${state.travelers.find((t) => t.id === idea.suggested_for)?.name ?? 'someone'}`}
                      </span>
                    )}
                  </h3>
                  {idea.city && <p className="muted">{idea.city}</p>}
                  {idea.why && <p>{idea.why}</p>}
                  {group && (
                    <>
                      <p className="chips tally">
                        {(['need', 'want'] as Mark[]).map((value) => {
                          const names = who(idea, value)
                          return (
                            <span key={value} className={names.length ? 'count' : 'count none'}>
                              <span className="label">{LABEL[value]}: {names.length} of {state.travelers.length}</span>
                              {names.map((name) => <span key={name} className="chip">{name}</span>)}
                            </span>
                          )
                        })}
                      </p>
                      <Chips label={LABEL.skip} items={who(idea, 'skip')} />
                    </>
                  )}
                </div>
                <div className="marks" role="group" aria-label={`Your mark for ${idea.name}`}>
                  {MARKS.map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      className={`mark-${value}`}
                      aria-pressed={marks[idea.id] === value}
                      disabled={busy || searching}
                      onClick={() => mark(idea, value)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {state.ideas.length > 0 && (
        <div className="suggest-more">
          <button disabled={busy || searching || findingMore || !marked} onClick={() => onMore(picks())}>
            {findingMore ? <><i className="spinner" />Finding more based on your picks…</> : 'Suggest more like this'}
          </button>
          <span className="muted">
            {findingMore
              ? 'Keep marking meanwhile. New places show up here for everyone on the trip.'
              : more === 'pending' || more === 'failed'
                ? "Couldn't find more right now. Try again in a moment."
                : marked
                  ? 'The agents find more places like the ones you marked must do or interested.'
                  : 'Mark a few places first, so the agents know what you like.'}
          </span>
        </div>
      )}

      <form className="add-idea panel" onSubmit={add}>
        <h2>Add a place</h2>
        <p className="muted">Something the agents missed? Add it for everyone; it's researched when planning starts.</p>
        <div className="row">
          <input required aria-label="Place" placeholder="Ghibli Museum" value={place.name}
                 onChange={(e) => setPlace({ ...place, name: e.target.value })} />
          <input aria-label="City (optional)" placeholder="City (optional)" value={place.city}
                 onChange={(e) => setPlace({ ...place, city: e.target.value })} />
          <button disabled={busy || searching}>Add</button>
        </div>
      </form>

      <button className="primary big" disabled={busy || searching} onClick={() => onSave(picks())}>Save my picks</button>
    </section>
  )
}
