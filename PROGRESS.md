# Progress

## Done

- Chose `/docs` as the GitHub Pages root.
- Added empty, schema-valid `docs/data/federal.json`, `trades.json`, and `status.json`.
- Documented the item schema in `docs/data/SCHEMA.md`.
- Added the display name as the single `name` value in `docs/js/config.js`, plus shared CSS and a small shared script.
- Added home (`docs/index.html`) and about (`docs/about.html`).
- Added the federal actions page (`docs/federal.html`, `docs/js/federal.js`). It loads `data/federal.json` and filters by text and `kind` in the browser.
- Added the congressional trades page (`docs/trades.html`, `docs/js/trades.js`). It loads `data/trades.json`, writes a short line per filing, and filters by member, chamber, party, and date.
- Added the status page (`docs/status.html`, `docs/js/status.js`). It loads `data/status.json` and lists last run, records, and errors per scraper.
- Added a noscript note, a plain favicon, and a small headline fix so "exchange" reads as "an exchange". Federal search and type sit on one row on wide screens.
- README explains the `/docs` layout, the empty JSON feeds, local preview, and how to turn on GitHub Pages.
- Checked the five pages in Chrome against a local static server: empty states, nav between pages, desktop and mobile layout, and filters using intercepted sample JSON. That sample is not committed.
- Merged to `main` (fast-forward). Pull request: https://github.com/Futurewhitehat2024/civic-tracker/pull/1

- Added the scraper package skeleton: polite HTTP client, key redaction, JSON feed merge, per-source cursor files, and schema checks for `docs/data/SCHEMA.md`.

## In progress

Federal actions scraper (Federal Register, House and Senate roll calls, Congress.gov bills). GitHub Pages is still off. Creating the Pages site returned 403, "Resource not accessible by integration". The token used here is not a repo admin. This work will not turn Pages on.

## Next step

Write and live-test the federal actions scraper, then commit that milestone before the trades scraper.

## Decisions

- Plain HTML, CSS, and vanilla JS. No framework and no build step.
- Site files live in `/docs` so Pages can serve `main` / `/docs`. A `.nojekyll` file disables Jekyll processing.
- Feeds fetch relative `data/*.json` URLs so the same files work on a project-pages subpath and on a local static server.
- Empty feeds stay empty. No sample records in the JSON files. Example objects live only in the schema doc.
- The visible site name is read from `docs/js/config.js` so a rename does not require editing each page.
- Filter controls run in the browser on the fetched JSON. They are usable once scrapers fill the files. There is no separate filter API.
- Trade headlines are built in `docs/js/trades.js` from the item fields. The JSON stores the filing fields, not a prewritten sentence.
- Links are rendered only for absolute `http` and `https` URLs.
- Scrapers write the three files in `docs/data/` from `SCHEMA.md`. They do not build the spec's per-entity `data/us/` tree or the Astro site. The site is already plain HTML.
- Python package `scrapers/`. GitHub Actions will run it. No paid APIs and no model calls.
- `DATA_GOV_API_KEY` is read only from the environment. It is not committed, not logged, and stripped from any URL before a URL is saved. Missing key skips Congress.gov and says so in `status.json`.
- Cursor files live in `state/<source>.json`, outside `/docs`, so a rerun can resume. Feeds dedupe by `id`.
- Requests send `CivicTracker-bot/1.0` and wait about a second between calls to the same official host. `efdsearch.senate.gov` is blocked in the client. Senate search automation stays off.

## Open questions

- Pages hosting: this environment cannot enable it. A repo admin still needs to turn on `main` / `/docs`.
- The api.data.gov key is not in this environment. Congress.gov stays skipped until `DATA_GOV_API_KEY` is set as an Actions secret.
