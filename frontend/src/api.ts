import type { DecisionAction, Picks, TestCard, TravelerIn, TripRequest, TripView } from './types'

/** The traveler this tab is acting as (from their own trip link); sent with every request. */
let traveler = ''
export function actAs(travelerId: string | null) {
  traveler = travelerId ?? ''
}

async function request(path: string, init: RequestInit = {}): Promise<TripView> {
  const headers = new Headers(init.headers)
  if (traveler) headers.set('X-Traveler', traveler)
  const res = await fetch(`/api/trips${path}`, { ...init, headers })
  if (!res.ok) throw new Error(await errorDetail(res))
  return res.json()
}

function post(path: string, body?: unknown): Promise<TripView> {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

/** Errors are `{detail: string}`; request validation errors are `{detail: [{loc, msg}]}`. */
async function errorDetail(res: Response): Promise<string> {
  try {
    const { detail } = await res.json()
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d: { loc: string[]; msg: string }) => `${d.loc.slice(1).join('.')}: ${d.msg}`).join('; ')
    }
  } catch {
    // not JSON (for example the dev proxy when the backend is down)
  }
  return `Request failed (${res.status} ${res.statusText})`
}

export const api = {
  createTrip: (trip: TripRequest) => post('', trip),
  getTrip: (id: string) => request(`/${id}`),
  eventsUrl: (id: string) => `/api/trips/${id}/events`,
  chooseDates: (id: string, start: string) => post(`/${id}/dates`, { start }),
  join: (id: string, traveler: TravelerIn) => post(`/${id}/travelers`, traveler),
  leave: (id: string, travelerId: string) => request(`/${id}/travelers/${travelerId}`, { method: 'DELETE' }),
  savePicks: (id: string, travelerId: string, picks: Picks) =>
    request(`/${id}/travelers/${travelerId}/picks`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(picks),
    }),
  addIdea: (id: string, name: string, city: string) => post(`/${id}/ideas`, { name, city }),
  suggestMore: (id: string, picks: Picks) => post(`/${id}/ideas/more`, picks),
  plan: (id: string) => post(`/${id}/plan`),
  retry: (id: string) => post(`/${id}/retry`),
  confirmChoices: (id: string, travelerId: string, flight_id: string | null, stay_ids: string[]) =>
    request(`/${id}/travelers/${travelerId}/choices`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flight_id, stay_ids }),
    }),
  decide: (id: string, action: DecisionAction, card: string, option_id?: string) =>
    post(`/${id}/decisions`, { action, card, option_id }),
  applyBudget: (id: string, traveler: string) => post(`/${id}/budget/apply`, { traveler }),
  moveItem: (id: string, item_id: string, day: string) => post(`/${id}/itinerary/move`, { item_id, day }),
  swapItem: (id: string, item_id: string, attraction_id: string) =>
    post(`/${id}/itinerary/swap`, { item_id, attraction_id }),
  approvePayment: (id: string, card: TestCard) => post(`/${id}/payments`, { card }),
  backOut: (id: string) => request(`/${id}/payments`, { method: 'DELETE' }),
}
