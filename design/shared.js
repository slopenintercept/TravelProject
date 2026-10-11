// Shared by the three direction mockups. Content is copied from a real saved trip (trip_99aaaeb1), not invented.

const IDEAS = [
  ['Tokyo Disneyland', 'Tokyo', 'Family', 'Iconic theme park, a stated trip focus.'],
  ['Tokyo DisneySea', 'Tokyo', 'Family', 'One-of-a-kind themed park, 20,000 Leagues ride.'],
  ['Ghibli Museum', 'Tokyo', 'Family', 'Whimsical Studio Ghibli art; book early.'],
  ['Odaiba waterfront', 'Tokyo', 'Family', 'Gundam, museums, Rainbow Bridge views.'],
  ['teamLab Planets', 'Tokyo', 'Culture', 'Barefoot, water-immersive digital art; a stated interest.'],
  ['Meiji Shrine', 'Tokyo', 'Culture', 'Serene forested shrine amid the city.'],
  ['Senso-ji Temple & Nakamise', 'Tokyo', 'Culture', "Asakusa's oldest temple and shopping street."],
  ['Akihabara', 'Tokyo', 'Culture', 'Electric town for anime, games, tech.'],
  ['Gion district stroll', 'Kyoto', 'Culture', 'Historic geisha quarter, evening atmosphere.'],
  ['Kyoto tea ceremony', 'Kyoto', 'Culture', 'Traditional matcha experience in a machiya.'],
  ['Shibuya Crossing', 'Tokyo', 'Sights', 'World-famous scramble crossing, quintessential Tokyo energy.'],
  ['Tokyo Skytree', 'Tokyo', 'Sights', 'Towering observation deck with city views.'],
  ['Fushimi Inari Taisha', 'Kyoto', 'Sights', 'Endless torii gates; go at sunrise.'],
  ['Kinkaku-ji Golden Pavilion', 'Kyoto', 'Sights', 'Gold-leaf temple mirrored in a pond.'],
  ['Kiyomizu-dera Temple', 'Kyoto', 'Sights', 'Wooden stage with sweeping city views.'],
  ['Tsukiji Outer Market', 'Tokyo', 'Food', 'Fresh sushi and street food stalls.'],
  ['Nishiki Market', 'Kyoto', 'Food', "Kyoto's kitchen, packed with local eats."],
  ['Golden Gai', 'Tokyo', 'Nightlife', 'Narrow alleys of tiny themed bars in Shinjuku.'],
  ['Shinjuku nightlife & izakaya', 'Tokyo', 'Nightlife', 'Bustling district for drinks and late food.'],
  ['Hakone day trip', 'Hakone', 'Nature', 'Mt. Fuji views, Lake Ashi, onsen soak.'],
  ['Arashiyama Bamboo Grove', 'Kyoto', 'Nature', 'Towering bamboo forest; arrive early.'],
  ['Kamakura Great Buddha', 'Kamakura', 'Day trips', 'Giant bronze Buddha and temple trails.'],
  ['Nikko shrines', 'Nikko', 'Day trips', 'Ornate UNESCO shrines and waterfalls.'],
  ['Nara deer park', 'Nara', 'Day trips', 'Friendly free-roaming deer and great Buddha.'],
].map(([name, city, category, why]) => ({ name, city, category, why }))

// A few marks already made, so the mock shows every state.
const PRESET = {
  'Tokyo Disneyland': 'must', 'Tokyo DisneySea': 'must', 'Ghibli Museum': 'must', 'Kamakura Great Buddha': 'must',
  'teamLab Planets': 'like', 'Fushimi Inari Taisha': 'like', 'Meiji Shrine': 'like',
  'Golden Gai': 'no',
}

const DAYS = [
  ['Wed', 'Jun 16', 'Tokyo', 27, 20, 67], ['Thu', 'Jun 17', 'Tokyo', 29, 21, 33], ['Fri', 'Jun 18', 'Tokyo', 27, 21, 67],
  ['Sat', 'Jun 19', 'Kyoto', 32, 19, 0], ['Sun', 'Jun 20', 'Kyoto', 29, 21, 33], ['Mon', 'Jun 21', 'Tokyo', 27, 21, 67],
  ['Tue', 'Jun 22', 'Tokyo', 28, 20, 0],
].map(([dow, date, city, hi, lo, rain]) => ({ dow, date, city, hi, lo, rain }))

// who: 'all' | 'alex' | 'friend2'
const ITEMS = [
  [0, '21:15', '23:45', 'fixed', 'Landed; transfer to the hotels', 'all'],
  [1, '09:00', '19:00', 'do', 'Tokyo Disneyland', 'all'],
  [2, '09:00', '19:00', 'do', 'Tokyo DisneySea', 'all'],
  [3, '09:00', '12:00', 'fixed', 'Tokyo → Kyoto', 'all'],
  [3, '12:00', '13:30', 'do', 'Gion District Stroll', 'friend2'],
  [3, '14:00', '15:30', 'do', 'Kiyomizu-dera Temple', 'all'],
  [4, '10:00', '10:45', 'do', 'Kyoto Tea Ceremony', 'friend2'],
  [4, '11:15', '13:15', 'do', 'Fushimi Inari Taisha', 'all'],
  [5, '09:00', '12:00', 'fixed', 'Kyoto → Tokyo', 'all'],
  [5, '12:00', '15:00', 'do', 'Ghibli Museum', 'all'],
  [5, '15:55', '17:25', 'do', 'Meiji Shrine', 'all'],
  [5, '17:55', '19:55', 'do', 'Nara Deer Park', 'alex'],
  [5, '18:25', '19:25', 'do', 'Shibuya Crossing', 'friend2'],
  [6, '08:00', '10:00', 'do', 'teamLab Planets', 'all'],
  [6, '10:30', '12:00', 'do', 'Senso-ji Temple & Nakamise', 'all'],
  [6, '12:27', '16:20', 'fixed', 'Airport for the flights home', 'all'],
].map(([day, start, end, kind, title, who]) => ({ day, start, end, kind, title, who }))

const AGENTS = ['Route', 'Profile', 'Timeframe', 'Ideas', 'Draft', 'Flight · Alex', 'Flight · friend2', 'Lodging',
  'Attractions', 'Transport', 'Weather', 'Scheduler', 'Budget', 'Validate']

const hours = (t) => { const [h, m] = t.split(':').map(Number); return h + m / 60 }

function byCategory(ideas) {
  const groups = new Map()
  for (const idea of ideas) groups.set(idea.category, [...(groups.get(idea.category) ?? []), idea])
  return [...groups]
}

// One screen is visible at a time, chosen by the URL hash: #start, #picks, #review.
function showScreen() {
  const id = location.hash.slice(1) || 'start'
  document.querySelectorAll('.screen').forEach((s) => s.classList.toggle('on', s.id === id))
  window.scrollTo(0, 0)
}
addEventListener('hashchange', showScreen)
addEventListener('DOMContentLoaded', () => { showScreen(); tally() })

// Picks: clicking a choice marks the card; clicking it again clears it.
document.addEventListener('click', (e) => {
  const button = e.target.closest('[data-pick]')
  if (!button) return
  const card = button.closest('[data-idea]')
  card.dataset.choice = card.dataset.choice === button.dataset.pick ? '' : button.dataset.pick
  tally()
})

function tally() {
  // Each direction file holds one picks screen, so every idea card on the page belongs to it.
  const cards = [...document.querySelectorAll('[data-idea]')]
  document.querySelectorAll('[data-tally]').forEach((el) => {
    const want = el.dataset.tally === 'none' ? '' : el.dataset.tally
    el.textContent = cards.filter((c) => (c.dataset.choice || '') === want).length
  })
}
