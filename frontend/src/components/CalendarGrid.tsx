import { useState } from 'react'
import { clock, daysBetween, monthDay, weekday } from '../format'
import type { ItineraryItem, Traveler } from '../types'

const HOUR_PX = 44
const MIN_START = 8 * 60 // the grid shows at least 08:00 to 21:00, wider if something falls outside
const MIN_END = 21 * 60

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

interface Props {
  items: ItineraryItem[]
  travelers: Traveler[]
  /** Who is looking: offered first in the view picker. */
  you?: Traveler
  busy?: boolean
  /** Dragging a block onto another day moves it there (fixed blocks, like flights, stay put). */
  onMove?: (itemId: string, day: string) => void
  /** Clicking a block selects it; the caller shows what can be done with it. */
  onSelect?: (item: ItineraryItem) => void
  selectedId?: string | null
  /** Messages for items that break a rule (shown as a red outline and in the tooltip). */
  problems?: Map<string, string[]>
  /** Extra line under a day's date, such as the weather. */
  dayNote?: (day: string) => string | undefined
}

/** A week-view calendar: a column per day, a block per activity sized by its time; split-offs side by side. */
export function CalendarGrid({ items, travelers, you, busy, onMove, onSelect, selectedId, problems, dayNote }: Props) {
  const [viewer, setViewer] = useState('') // a traveler id, or '' for everyone
  const [dragId, setDragId] = useState<string | null>(null)
  const [overDay, setOverDay] = useState<string | null>(null)
  if (items.length === 0) return <p className="muted">Nothing on the calendar yet.</p>

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
  const hours = Array.from({ length: (bottom - top) / 60 }, (_, i) => top / 60 + i)
  const order = you ? [you, ...travelers.filter((t) => t.id !== you.id)] : travelers

  return (
    <div className="calendar-grid-wrap">
      {everyone > 1 && (
        <div className="viewer" role="radiogroup" aria-label="View">
          <strong>View</strong>
          <div className="segmented">
            {[{ id: '', name: 'Everyone' }, ...order.map((t) => ({ id: t.id, name: t.id === you?.id ? 'Just me' : t.name }))].map((t) => (
              <label key={t.id}>
                <input type="radio" name="calendar-viewer" checked={viewer === t.id} onChange={() => setViewer(t.id)} />
                <span>{t.name}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="calendar-grid" style={{ gridTemplateColumns: `52px repeat(${days.length}, minmax(130px, 1fr))` }}>
        <div className="corner" />
        {days.map((day) => {
          const city = [...new Set(items.filter((i) => i.day === day && i.kind === 'attraction').map((i) => i.city))].join(' / ')
            || items.find((i) => i.day === day)?.city
          const note = dayNote?.(day)
          return (
            <div key={day} className="day-head">
              <strong>{weekday(day)} {monthDay(day)}</strong>
              {city && <span>{city}</span>}
              {note && <span className="note">{note}</span>}
            </div>
          )
        })}

        <div className="hours" style={{ height: hours.length * HOUR_PX }}>
          {hours.map((h) => <div key={h} style={{ height: HOUR_PX }}>{String(h).padStart(2, '0')}:00</div>)}
        </div>
        {days.map((day) => (
          <div
            key={day}
            className={overDay === day ? 'day-col over' : 'day-col'}
            style={{ height: hours.length * HOUR_PX, backgroundSize: `100% ${HOUR_PX}px` }}
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
              const split = item.kind === 'attraction' && item.travelers.length < everyone
              const issues = problems?.get(item.id)
              const movable = !!onMove && !item.locked && !busy
              return (
                <div
                  key={item.id}
                  className={[
                    'block', `kind-${item.kind}`, split && 'split', issues && 'conflict',
                    selectedId === item.id && 'selected', dragId === item.id && 'dragging', onSelect && !item.locked && 'clickable',
                  ].filter(Boolean).join(' ')}
                  style={{
                    top: ((start - top) / 60) * HOUR_PX,
                    height: (length / 60) * HOUR_PX - 2,
                    left: `calc(${(lane / lanes) * 100}% + 2px)`,
                    width: `calc(${100 / lanes}% - 4px)`,
                  }}
                  title={[item.title, `${clock(item.start)}–${clock(item.end)}`, names(item.travelers), ...(issues ?? [])].join('\n')}
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
                  onClick={() => !item.locked && onSelect?.(item)}
                >
                  <div className="title">{item.title}</div>
                  <div className="time">{clock(item.start)}–{clock(item.end)}</div>
                  {item.kind === 'attraction' && <div className="who">{names(item.travelers)}</div>}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
