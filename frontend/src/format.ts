const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
export const money = (amount: number) => usd.format(amount)

export const temp = (celsius: number) => `${Math.round(celsius)}°C`

/** "HH:MM:SS" -> "HH:MM" */
export const clock = (time: string) => time.slice(0, 5)

/** "YYYY-MM-DD" as a local date (`new Date("YYYY-MM-DD")` would read it as UTC). */
const toDate = (day: string) => new Date(`${day}T00:00:00`)

const toDay = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

export const weekday = (day: string) => toDate(day).toLocaleDateString('en-US', { weekday: 'short' })
export const monthDay = (day: string) => toDate(day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
export const dateRange = (start: string, end: string) =>
  `${weekday(start)}, ${monthDay(start)} – ${weekday(end)}, ${monthDay(end)}`

export function tomorrow(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return toDay(d)
}

/** Every day from `first` to `last`, inclusive. */
export function daysBetween(first: string, last: string): string[] {
  const days: string[] = []
  for (const d = toDate(first), end = toDate(last); d <= end; d.setDate(d.getDate() + 1)) days.push(toDay(d))
  return days
}


/** "3 places", "1 place" */
export const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']
/** Small numbers as words, for headlines: "three stays". */
export const inWords = (n: number) => WORDS[n] ?? String(n)
export const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** Who something is for, by name: the whole group reads as "Everyone". */
export const whoIsIn = (names: string[], groupSize: number) => (names.length === groupSize ? ['Everyone'] : names)

/** Links come from agent research, so only http(s) and same-origin paths become clickable. */
export const safeHref = (url: string | null) => (url && /^(https?:\/\/|\/)/i.test(url) ? url : undefined)
