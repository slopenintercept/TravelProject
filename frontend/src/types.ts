// Mirrors backend/tripwright/models.py, cards.py, api.py and the SSE events.
// Dates are "YYYY-MM-DD", datetimes are naive local ISO strings, times are "HH:MM:SS".

export type Pace = 'relaxed' | 'balanced' | 'packed'
export type Category = 'flights' | 'lodging' | 'attractions' | 'transport'
export const CATEGORIES: Category[] = ['flights', 'lodging', 'attractions', 'transport']

// --- models.py -------------------------------------------------------------------

export interface Source {
  url: string
  title: string
  evidence_url: string | null
  fetched_at: string | null
}

/** What each person fills in: where they fly from, their budget, and what they need vs want to see. */
export interface TravelerIn {
  name: string
  origin: string
  budget_usd: number
  need: string[]
  want: string[]
}

/** The host's form: the trip itself plus the host's own preferences. */
export interface TripRequest extends TravelerIn {
  destination: string
  days: number
  start_date: string | null
  pace: Pace
}

export interface TravelerProfile {
  home: string
  interests: string[]
  pace: Pace
  stated_preferences: string[]
  summary: string
}

export interface RouteSegment {
  city: string
  nights: number
}

export interface RoutePlan {
  segments: RouteSegment[]
  arrival_day_offset: number
}

export interface DateWindow {
  id: string
  start: string // depart origin
  end: string // depart destination
  avg_high_c: number | null
  avg_low_c: number | null
  rainy_days: number | null
  weather_summary: string
  crowd_level: 'low' | 'moderate' | 'high'
  cheapest_fare_usd: number | null
  price_trend: string
  notes: string
  reasoning: string
  sources: Source[]
}

export interface TripDates {
  start: string
  arrival: string
  end: string
}

export interface FlightOption {
  id: string
  airline: string
  origin: string
  destination: string
  depart_at: string
  arrive_at: string
  return_depart_at: string | null
  return_arrive_at: string | null
  duration_minutes: number
  stops: number
  layovers: string[]
  price_usd: number // round trip, per traveler
  booking_url: string
  source: Source
  tradeoff: string
}

export interface FlightPlan {
  origin_airports: string[]
  options: FlightOption[]
  selected_id: string
}

export interface CommonChoice {
  choice: string
  because: string
  alternative: string
  details: string[]
  sources: Source[]
}

export interface LodgingOption {
  id: string
  city: string
  name: string
  kind: 'hotel' | 'airbnb'
  neighborhood: string
  check_in: string
  check_out: string
  price_total_usd: number
  rating: number | null
  location_note: string
  lat: number | null
  lon: number | null
  booking_url: string
  source: Source
}

export interface LodgingStay {
  city: string
  check_in: string
  check_out: string
  selected_id: string
  options: LodgingOption[]
  reasoning: string
}

export interface LodgingPlan {
  common_choice: CommonChoice
  stays: LodgingStay[]
}

/** One person on the trip, with their own flight and their own rooms picked to their own budget. */
export interface Traveler extends TravelerIn {
  id: string
  host: boolean
  flights: FlightPlan | null
  lodging: LodgingPlan | null // this traveler's room for each stay, chosen from the group's options
}

export interface Attraction {
  id: string
  name: string
  city: string
  must_have: boolean // someone needs to see it
  need_by: string[] // traveler ids
  want_by: string[]
  why: string
  duration_minutes: number
  ticket_price_usd: number // per traveler
  opens: string | null
  closes: string | null
  closed_weekdays: number[] // Monday = 0
  outdoor: boolean
  availability_note: string
  lat: number | null
  lon: number | null
  booking_url: string | null
  source: Source
  included: boolean
}

export interface TransportLeg {
  id: string
  kind: 'intercity' | 'airport_transfer' | 'local_pass' | 'rental_car'
  from_place: string
  to_place: string
  mode: string
  duration_minutes: number
  price_usd: number
  per_person: boolean
  notes: string
  booking_url: string | null
  source: Source
  included: boolean
}

export interface TransportPlan {
  common_choice: CommonChoice
  rideshare_note: string
  legs: TransportLeg[]
}

export interface DayWeather {
  day: string
  city: string
  high_c: number | null
  low_c: number | null
  precip_prob: number | null // 0-100
  summary: string
  kind: 'forecast' | 'climate'
  source: Source
}

export interface ItineraryItem {
  id: string
  day: string
  start: string
  end: string
  kind: 'arrival' | 'departure' | 'travel' | 'attraction'
  title: string
  city: string
  ref_id: string | null
  cost_usd: number
  travelers: string[] // ids of who is there; fewer than everyone means a split-off
  locked: boolean // flights and intercity travel can't be dragged
  pinned: boolean // the user put this on this day
}

export interface Unscheduled {
  attraction_id: string
  name: string
  reason: string
  wanted_by: string[] // traveler ids who needed or wanted it
}

export interface Violation {
  code: string
  message: string
  item_ids: string[]
  severity: 'error' | 'warning'
}

export interface BudgetSummary {
  total_usd: number
  by_category: Record<string, number>
  allotted: Record<string, number>
  spent_usd: number
  remaining_usd: number
}

export interface Swap {
  category: string
  action: 'swap' | 'remove'
  from_id: string
  to_id: string | null
  title: string
  saves_usd: number
}

export interface SwapProposal {
  swaps: Swap[]
  new_total_usd: number
  fits: boolean
}

export type AgentStatusName =
  | 'idle'
  | 'working'
  | 'under_review'
  | 'sent_back'
  | 'accepted'
  | 'fallback'
  | 'pending'
  | 'failed'

export interface AgentStatus {
  agent: string
  status: AgentStatusName
  attempt: number
  message: string
  found: string
}

export interface Flag {
  kind: 'fallback' | 'pending'
  reason: string
}

export interface TripState {
  id: string
  request: TripRequest
  // gathering: dates are set and the host is waiting for invited travelers' preferences.
  stage: 'created' | 'timeframe' | 'awaiting_dates' | 'gathering' | 'planning' | 'review'
  travelers: Traveler[] // the host first
  profile: TravelerProfile | null
  route: RoutePlan | null
  windows: DateWindow[]
  dates: TripDates | null
  lodging: LodgingPlan | null // what the lodging agent found: the options for each stay
  attractions: Attraction[]
  transport: TransportPlan | null
  weather: DayWeather[]
  itinerary: ItineraryItem[]
  unscheduled: Unscheduled[]
  violations: Violation[]
  plan_note: string // "One shared itinerary", or who splits off and when
  budgets: Record<string, BudgetSummary> // keyed by traveler id
  budget_proposals: Record<string, SwapProposal> // keyed by traveler id
  flags: Record<string, Flag> // keyed by agent name: "flight:<traveler>", "lodging", "attractions", ...
  approvals: Record<string, 'approved'> // keyed by card id
  agents: Record<string, AgentStatus> // keyed by agent name
  lodging_override: 'hotel' | 'airbnb' | null
  transport_override: 'rental_car' | null
}

// --- cards.py --------------------------------------------------------------------

export interface Alternative {
  id: string
  title: string
  detail: string
  price_usd: number
}

export interface Card {
  // "flight:<traveler>", "stay:<traveler>:<n>", "attraction:<id>", "leg:<id>", or the defaults "lodging" / "transport"
  id: string
  category: Category
  kind: 'item' | 'default' // "default" is the most-travelers-pick card
  traveler: string | null // whose flight or stay this is (traveler id); null for shared cards
  title: string
  detail: string
  price_usd: number
  reasoning: string
  sources: Source[]
  booking_url: string | null
  status: 'proposed' | 'approved' | 'removed'
  must_have: boolean
  flag: Flag | null
  alternatives: Alternative[]
  switch_label: string | null
  // Attractions only: names of who needs it, who wants it, and who is going.
  need_by: string[]
  want_by: string[]
  going: string[]
}

// --- api.py ----------------------------------------------------------------------

// --- booking.py ------------------------------------------------------------------

export interface BookingStep {
  id: string
  category: Category
  traveler: string | null // whose booking this is (traveler id); null for shared tickets and transport
  who: string[] // names of the people this is for
  title: string
  when: string
  provider: string
  filled: string[] // details the link already carries into the provider's page
  todo: string // what is left to choose or enter there
  price_usd: number
  url: string | null // null: nothing to book
  link: 'filled' | 'booking' | 'info'
}

export interface TripView {
  state: TripState
  cards: Card[]
  booking: BookingStep[]
  busy: boolean
  message: string
}

export type DecisionAction = 'approve' | 'remove' | 'restore' | 'swap' | 'switch'

// --- GET /api/trips/{id}/events --------------------------------------------------
// `agent` is a specialist ("lodging") or one traveler's flight specialist ("flight:<traveler>").

export type TripEvent = { ts: number } & (
  | ({ type: 'agent' } & AgentStatus)
  | { type: 'tool'; agent: string; tool: string; input: unknown }
  | { type: 'text'; agent: string; text: string }
  | { type: 'stage'; stage: string; status: 'started' | 'finished' }
  | { type: 'state' }
  | { type: 'error'; message: string }
)
