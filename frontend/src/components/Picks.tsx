import { useState, type FormEvent } from 'react'
import type { Idea, Picks as Marks, Traveler, TripState } from '../types'
import { AgentTag } from './Agents'
import { Board } from './Board'
import { DraftPlan, placeKey } from './DraftPlan'
import { Crew } from './Working'

type Mark = keyof Marks

// The row has room for a short word; the tallies spell "not for me" out.
const MARKS: [Mark, string][] = [
  ['need', 'Must do'],
  ['want', 'Interested'],
  ['skip', 'No'],
]
const STILL_WORKING = ['working', 'under_review', 'sent_back']

/** A traveler's mark on a place, if any. */
function markOf(t: Traveler, idea: Idea): Mark | null {
  return MARKS.map(([mark]) => mark).find((mark) => t[mark].some((name) => placeKey(name) === placeKey(idea.name))) ?? null
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

/** "What sounds good?": everyone marks the same list of places the agents found, and can add their own.
 *  The draft plan beside it shows where the group's picks land. */
export function Picks({ state, you, busy, onSave, onAdd, onMore }: Props) {
  const [marks, setMarks] = useState<Record<string, Mark>>(() =>
    Object.fromEntries(state.ideas.flatMap((idea) => {
      const mark = markOf(you, idea)
      return mark ? [[idea.id, mark]] : []
    })),
  )
  const [adding, setAdding] = useState(false)
  const [place, setPlace] = useState({ name: '', city: '' })
  const status = state.agents.ideas?.status
  const searching = !!status && STILL_WORKING.includes(status)
  const more = state.agents[`more_ideas:${you.id}`]?.status
  const findingMore = !!more && STILL_WORKING.includes(more)
  const group = state.travelers.length > 1
  const marked = Object.keys(marks).length > 0
  const tally = (value: Mark) => state.ideas.filter((idea) => marks[idea.id] === value).length

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
    if (await onAdd(place.name.trim(), place.city.trim())) {
      setPlace({ name: '', city: '' })
      setAdding(false)
    }
  }

  return (
    <>
      <main className="feed">
        <div className="hd top">
          <h1 className="display h-40">What sounds good?</h1>
          <AgentTag agent="ideas" />
        </div>
        <p className="say">
          {searching
            ? `Agents are finding places to see and things to do in ${state.request.destination}…`
            : state.ideas.length > 0
              ? 'Mark what you must do, what interests you, and what is not for you. Leave the rest blank.'
              : "The agents couldn't suggest places for this trip. Add the places you want below."}
        </p>
        {searching && <Crew />}

        {[...groups].map(([category, ideas]) => (
          <section key={category}>
            <div className="hd">
              <h2>{category}</h2>
              {/* Places people added themselves have no agent behind them. */}
              {ideas.some((idea) => !idea.added_by) && <AgentTag agent="ideas" words={`${ideas.length} found`} />}
            </div>
            {ideas.map((idea) => {
              const others = group
                ? MARKS.map(([value, label]) => [label, who(idea, value)] as const).filter(([, names]) => names.length > 0)
                : []
              return (
                <article key={idea.id} className="idea" data-choice={marks[idea.id] ?? ''}>
                  <div className="what">
                  <b>
                    {idea.name}
                    {idea.city && <small>{idea.city}</small>}
                    {idea.suggested_for && (
                      <small>
                        {idea.suggested_for === you.id
                          ? 'New, suggested for you'
                          : `Suggested for ${state.travelers.find((t) => t.id === idea.suggested_for)?.name ?? 'someone'}`}
                      </small>
                    )}
                  </b>
                  {idea.why && <p>{idea.why}</p>}
                  {others.length > 0 && <p>{others.map(([label, names]) => `${label}: ${names.join(', ')}`).join(' · ')}</p>}
                  </div>
                  <div className="choices" role="group" aria-label={`Your mark for ${idea.name}`}>
                    {MARKS.map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={marks[idea.id] === value}
                        title={value === 'skip' ? 'Not for me' : undefined}
                        disabled={busy || searching}
                        onClick={() => mark(idea, value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </article>
              )
            })}
          </section>
        ))}

        <div className="go">
          <button className="pill" aria-expanded={adding} disabled={busy || searching} onClick={() => setAdding(!adding)}>
            Add a place
          </button>
          {state.ideas.length > 0 && (
            <button className="pill" disabled={busy || searching || findingMore || !marked} onClick={() => onMore(picks())}>
              {findingMore ? 'Finding more like your picks…' : 'More like my picks'}
            </button>
          )}
        </div>
        {adding && (
          <form className="add-place" onSubmit={add}>
            <input className="field" required autoFocus aria-label="Place" placeholder="Ghibli Museum" value={place.name}
                   onChange={(e) => setPlace({ ...place, name: e.target.value })} />
            <input className="field" aria-label="City (optional)" placeholder="City (optional)" value={place.city}
                   onChange={(e) => setPlace({ ...place, city: e.target.value })} />
            <button className="pill solid" disabled={busy || searching}>Add</button>
          </form>
        )}
        {(adding || state.ideas.length === 0) && (
          <p className="aside">Something the agents missed? Add it for everyone; it's researched when planning starts.</p>
        )}
        {state.ideas.length > 0 && (
          <p className="aside">
            {findingMore
              ? 'Keep marking meanwhile. New places show up here for everyone on the trip.'
              : more === 'pending' || more === 'failed'
                ? "Couldn't find more right now. Try again in a moment."
                : marked
                  ? 'The agents can find more places like the ones you marked must do or interested.'
                  : 'Mark a few places first, so the agents know what you like.'}
          </p>
        )}
      </main>

      <Board plan="Draft plan">
        <DraftPlan state={state} musts={state.ideas.filter((idea) => marks[idea.id] === 'need').map((idea) => idea.name)}>
          <div className="tallies">
            <span><b>{tally('need')}</b>must do</span>
            <span><b>{tally('want')}</b>interested</span>
            <span><b>{tally('skip')}</b>not for me</span>
            <span><b>{state.ideas.filter((idea) => !marks[idea.id]).length}</b>unmarked</span>
            <span className="grow" />
            <button className="pill solid" disabled={busy || searching} onClick={() => onSave(picks())}>Save my picks →</button>
          </div>
        </DraftPlan>
      </Board>
    </>
  )
}
