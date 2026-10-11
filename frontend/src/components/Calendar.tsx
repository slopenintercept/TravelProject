import { useState } from 'react'
import { clock, daysBetween, monthDay, weekday } from '../format'
import type { DayWeather, ItineraryItem, Traveler } from '../types'

const HOUR_PX = 35
const LINE_PX = 17
const MIN_START = 8 * 60 // the grid shows at least 08:00 to 24:00, earlier if something starts before
const MIN_END = 24 * 60

const minutes = (time: string) => Number(time.slice(0, 2)) * 60 + Number(time.slice(3, 5))

interface Placed {
  item: ItineraryItem
  lane: number
  lanes: number
}

/** Side-by-side lanes for items at the same time (the group splitting up), one cluster of overlaps at a time. */
function layout(items: ItineraryItem[]): Placed[] {
  const sorted = [...items].sort((a, b) => minutes(a.start) - minutes(b.start) || minutes(b.end) - minutes(a.end))
  const placed: Placed[] = []
  let cluster: Placed[] = []
  let clusterEnd = -1
  let laneEnds: number[] = []
  const close = () => {
    const lanes = Math.max(1, ...cluster.map((p) => p.lane + 1))
    for (const p of cluster) p.lanes = lanes
    placed.push(...cluster)
  }
  for (const item of sorted) {
    const start = minutes(item.start)
    if (start >= clusterEnd && cluster.length) {
      close()
      cluster = []
      laneEnds = []
    }
    let lane = laneEnds.findIndex((end) => end <= start)
    if (lane === -1) lane = laneEnds.length
    laneEnds[lane] = minutes(item.end)
    cluster.push({ item, lane, lanes: 1 })
    clusterEnd = Math.max(clusterEnd, minutes(item.end))
  }
  if (cluster.length) close()
  return placed
}

/** The city a day is spent in, from what is on it. */
export function cityOn(day: string, items: ItineraryItem[]): string | undefined {
  const visits = items.filter((i) => i.day === day && i.kind === 'attraction').map((i) => i.city)
  return [...new Set(visits)].join(' / ') || items.find((i) => i.day === day)?.city
}

interface Props {
  items: ItineraryItem[]
  travelers: Traveler[]
  /** Who is looking: what they do without everyone is pink, what only others do is mint. */
  you?: Traveler
  /** Show one traveler's days (a traveler id), or '' for everyone's. */
  viewer?: string
  /** The forecast for each day's header. */
  weather?: DayWeather[]
  busy?: boolean
  /** Dragging a block onto another day moves it there (fixed blocks, like flights, stay put). */
  onMove?: (itemId: string, day: string) => void
  /** Clicking a block selects it; the caller shows what can be done with it. */
  onSelect?: (item: ItineraryItem) => void
  selectedId?: string | null
  /** Messages for items that break a rule (shown as a coral outline and in the tooltip). */
  problems?: Map<string, string[]>
}

/** A week-view calendar: a column per day, a block per activity sized by its time; split-offs side by side. */
export function Calendar({ items, travelers, you, viewer = '', weather = [], busy, onMove, onSelect, selectedId, problems }: Props) {
  const [dragId, setDragId] = useState<string | null>(null)
  const [overDay, setOverDay] = useState<string | null>(null)
  if (items.length === 0) return <div className="ph">Nothing on the calendar yet.</div>

  function drop(day: string) {
    const item = items.find((i) => i.id === dragId)
    setDragId(null)
    setOverDay(null)
    if (item && item.day !== day) onMove?.(item.id, day)
  }

  const everyone = travelers.length
  const names = (ids: string[]) =>
    ids.length === everyone ? 'Everyone' : travelers.filter((t) => ids.includes(t.id)).map((t) => t.name).join(', ')
  const shown = viewer ? items.filter((i) => i.locked || i.travelers.includes(viewer)) : items
  const sorted = [...items].sort((a, b) => (a.day + a.start).localeCompare(b.day + b.start))
  const days = daysBetween(sorted[0].day, sorted[sorted.length - 1].day)
  const top = Math.min(MIN_START, ...items.map((i) => Math.floor(minutes(i.start) / 60) * 60))
  const bottom = Math.max(MIN_END, ...items.map((i) => Math.ceil(minutes(i.end) / 60) * 60))
  const height = ((bottom - top) / 60) * HOUR_PX
  const labels: number[] = [] // every other hour
  for (let h = Math.ceil(top / 120) * 2; h * 60 < bottom; h += 2) labels.push(h)

  return (
    <div className="calwrap">
      <div className="cal" style={{ gridTemplateColumns: `44px repeat(${days.length}, minmax(78px, 1fr))` }}>
        <div />
        {days.map((day) => {
          const forecast = weather.find((w) => w.day === day)
          const facts = [
            forecast?.city || cityOn(day, items),
            forecast?.high_c != null && `${Math.round(forecast.high_c)}°`,
            forecast?.precip_prob != null && `${Math.round(forecast.precip_prob)}% rain`,
          ].filter(Boolean)
          return (
            <div key={day} className="dh" title={forecast?.summary}>
              {weekday(day)} {monthDay(day)}
              <small>{facts.join(' · ')}</small>
            </div>
          )
        })}

        <div className="hours" style={{ height }}>
          {labels.map((h) => <span key={h} style={{ top: ((h * 60 - top) / 60) * HOUR_PX }}>{h}:00</span>)}
        </div>
        {days.map((day) => (
          <div
            key={day}
            className={overDay === day ? 'col drop' : 'col'}
            style={{ height, backgroundSize: `100% ${HOUR_PX}px` }}
            onDragOver={(e) => {
              if (!dragId) return
              e.preventDefault() // allows the drop
              setOverDay(day)
            }}
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOverDay(null)
            }}
            onDrop={(e) => {
              e.preventDefault()
              drop(day)
            }}
          >
            {layout(shown.filter((i) => i.day === day)).map(({ item, lane, lanes }) => {
              const start = minutes(item.start)
              const length = Math.max(minutes(item.end) - start, 20)
              const px = Math.max((length / 60) * HOUR_PX - 2, LINE_PX + 2) // never shorter than one line of its title
              const tight = px < LINE_PX + 12 // no room for the padding above and below that line
              const split = item.kind === 'attraction' && item.travelers.length < everyone
              const issues = problems?.get(item.id)
              const movable = !!onMove && !item.locked && !busy
              const selectable = !!onSelect && !item.locked
              // Show as many title lines as fit, and the times only where a spare line is left for them.
              const lines = tight ? 1 : Math.max(1, Math.floor((px - 12) / LINE_PX))
              const timed = lines >= 3 && lanes === 1
              return (
                <div
                  key={item.id}
                  className={[
                    'ev', item.locked && 'fixed', split && (you && item.travelers.includes(you.id) ? 'solo' : 'alt'),
                    issues && 'conflict', selectedId === item.id && 'sel', dragId === item.id && 'dragging',
                    selectable && 'clickable', tight && 'tight', lanes > 2 && 'narrow',
                  ].filter(Boolean).join(' ')}
                  style={{
                    top: ((start - top) / 60) * HOUR_PX,
                    height: px,
                    left: `calc(${(lane / lanes) * 100}% + 2px)`,
                    width: `calc(${100 / lanes}% - 4px)`,
                  }}
                  title={[item.title, `${clock(item.start)}–${clock(item.end)}`, names(item.travelers), ...(issues ?? [])].join('\n')}
                  role={selectable ? 'button' : undefined}
                  tabIndex={selectable ? 0 : undefined}
                  draggable={movable}
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', item.id) // Firefox needs data to start a drag
                    e.dataTransfer.effectAllowed = 'move'
                    setDragId(item.id)
                  }}
                  onDragEnd={() => {
                    setDragId(null)
                    setOverDay(null)
                  }}
                  onClick={() => selectable && onSelect?.(item)}
                  onKeyDown={(e) => {
                    if (!selectable || (e.key !== 'Enter' && e.key !== ' ')) return
                    e.preventDefault()
                    onSelect?.(item)
                  }}
                >
                  <span className="t" style={{ WebkitLineClamp: lines - (timed ? 1 : 0) }}>{item.title}</span>
                  {timed && <small>{clock(item.start)}–{clock(item.end)}</small>}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
