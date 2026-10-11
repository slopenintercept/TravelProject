# Handoff: a map on the draft plan

Written 2026-10-11 at about 05:00 Central by the chat that went through the redesign choices with the user. You implement this; that chat only checks on it.

## What the user asked for

> yes go ahead and implement a map but make sure its easy to implement we are low on time

The approved mockup (`design/reference/2-picks.jpg`, source `design/direction-c-lilac.html`) has a dashed box on the Picks board captioned "[ map — pins for every place on the list, Tokyo and Kyoto; picked ones filled ]". The built app left it out and shows the route as a row of city chips. Build that map, the simplest way that works. Time matters more than polish.

## Ground rules

- Read "Start here" and "Gotchas" in `HANDOFF.md` first. The user's global rules apply: minimum code, surgical changes, verify against a concrete check.
- Several chats share this working folder. Uncommitted work that is not yours is in it: a payments chat's (`frontend/src/App.tsx`, `api.ts`, `types.ts`, `styles.css`, `components/Finish.tsx`, `components/Pay.tsx`, several backend files) and deploy/docs changes (`deploy/`, `README.md`, `HANDOFF.md`, `.env.example`, `.gitignore`, `.dockerignore`). Two of your files, `types.ts` and `styles.css`, already carry the payments chat's edits: make small targeted edits, never rewrite a file whole, and check `git diff <file>` afterwards shows only your lines added to theirs.
- Do not commit, push or deploy. The user decides that.
- Do not restart or stop the server on port 8000; it is the user's. Never print `.env` or `.env.hosted`.
- `npm run build` replaces `frontend/dist`, which the user's server on port 8000 serves. Use the dev server while you work and build once at the end, when the map works.
- If Leaflet is still fighting you after about 30 minutes, stop and write what blocked you under "Result".

## The plan

Keep to this unless something in it turns out not to work.

1. **Add plain Leaflet.** `cd frontend && npm install leaflet && npm install -D @types/leaflet`. No `react-leaflet`, no API key. Both `package.json` and `package-lock.json` must change: the `Dockerfile` runs `npm ci`.
2. **One new component, `frontend/src/components/Map.tsx`,** about 50 lines.
   - Props: the places to pin, each `{ name, lat, lon, filled }`.
   - A `useEffect` creates `L.map` on a `div` ref, adds the tile layer, adds one `L.circleMarker` per place with its name as a tooltip, calls `fitBounds` over the pins, and returns `() => map.remove()`. React 19 runs effects twice in development; without that cleanup Leaflet throws "Map container is already initialized".
   - `import 'leaflet/dist/leaflet.css'` in that file.
   - Use `L.circleMarker`, not `L.marker`. The default marker needs image files that Vite does not find without extra setup.
   - Tiles: OpenStreetMap, `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, attribution `© OpenStreetMap contributors`. Leave Leaflet's attribution control visible.
   - Pins: outlined for every place, filled for the viewer's must-do places, in the purple the app already uses for marked places (`--pick` in `styles.css`). Read the colour from the CSS variable instead of repeating the hex.
   - Render nothing when no place has coordinates.
3. **Show it in `frontend/src/components/DraftPlan.tsx`,** right under the `<Route>` row (line 40). `DraftPlan` is what the board shows on Picks, Who's coming, Join, Agents working and Choose, so one insertion covers them all. It already has `state.ideas` and `musts` (names of the viewer's must-do places; compare names with `placeKey`, as the rest of that file does).
   - Keep the row of city chips.
   - Leave Start and the dates screen alone. `EmptyPlan` in `Route.tsx` has no places to pin yet.
4. **Data.** No backend change. Every place already has coordinates on the server: `Idea.lat` and `Idea.lon` in `backend/tripwright/models.py`, filled by `backend/tripwright/draft.py` when the draft plan is built. So they are `null` until the first draft exists, and stay `null` for a place the lookup could not find; skip those. The frontend type is missing the two fields: add `lat: number | null` and `lon: number | null` to `Idea` in `frontend/src/types.ts`.
5. **Style.** A few rules in `frontend/src/styles.css` next to `.route` (line 125): a fixed height of about 220px, the 22px radius that `.ph` uses, `overflow: hidden`, and `position: relative; z-index: 0` so Leaflet's panes (z-index up to 1000) stay under the app's own floating pieces, such as the confirm bar on Choose.
6. **Docs.** Two lines say there is no map; change both to say what was built: the "**No map.**" bullet under "Where this differs from the brief" in `README.md`, and the "**No map.**" bullet under "The redesign" in `HANDOFF.md`.

## How to check it

1. `cd frontend && npx tsc --noEmit` passes while you work; `npm run build` passes at the end.
2. See it in a browser without touching the user's trips. The recipe is in `HANDOFF.md` under Gotchas ("To click through the UI without touching any real data"):
   - a second backend on port **8011** with `DATA_DIR=<your scratch folder>` in front of the command, and `/api/health` saying `sqlite`;
   - copies of real trips saved into its SQLite file (`store.load_trip`, change `state.id`, save). Pick one whose ideas have coordinates, and set `stage` on copies to reach Picks and Choose;
   - the dev server: `TRIPWRIGHT_BACKEND=http://localhost:8011 npm run dev -- --port 5181 --strictPort`.
3. What must be true:
   - the tiles load and there is one pin per place that has coordinates;
   - must-do places are filled, and marking a place **Must do** on Picks fills its pin without a reload;
   - at 1280px and 1440px wide nothing scrolls sideways, and the confirm bar on Choose is not covered by the map;
   - the browser console has no errors.
4. Save one screenshot of Picks with the map as `design/implemented/15-picks-map.jpg`.

## When you finish

Add a section `## Result` at the bottom of this file: the files you changed, what you ran and what it showed, and anything left undone. Do the same if you stop early. Another chat reads this file every few minutes to see whether the work is done.
