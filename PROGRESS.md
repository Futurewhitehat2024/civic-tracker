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
- MILESTONE: federal actions scraper is written, live-tested, and writing `docs/data/federal.json` and `status.json`.

- House PTR scraper parses electronic filings and lists scanned PDFs as links. Senate eFD rows are links only. `docs/SENATE-EFD.md` records that the search is not automated.

## In progress

GitHub Actions schedule and `workflow_dispatch` date-range backfill. GitHub Pages is still off. Creating the Pages site returned 403, "Resource not accessible by integration". The token used here is not a repo admin. This work will not turn Pages on.

## Next step

Add the scheduled workflow with backfill inputs, and CI that runs the unit tests. Do not enable GitHub Pages.

## Decisions

- Plain HTML, CSS, and vanilla JS. No framework and no build step.
- Site files live in `/docs` so Pages can serve `main` / `/docs`. A `.nojekyll` file disables Jekyll processing.
- Feeds fetch relative `data/*.json` URLs so the same files work on a project-pages subpath and on a local static server.
- Example objects live only in the schema doc. `federal.json` holds the live window from the federal scraper. `trades.json` stays empty until the trades scraper runs.
- The visible site name is read from `docs/js/config.js` so a rename does not require editing each page.
- Filter controls run in the browser on the fetched JSON. They are usable once scrapers fill the files. There is no separate filter API.
- Trade headlines are built in `docs/js/trades.js` from the item fields. The JSON stores the filing fields, not a prewritten sentence.
- Links are rendered only for absolute `http` and `https` URLs.
- Scrapers write the three files in `docs/data/` from `SCHEMA.md`. They do not build the spec's per-entity `data/us/` tree or the Astro site. The site is already plain HTML.
- Python package `scrapers/`. GitHub Actions will run it. No paid APIs and no model calls.
- `DATA_GOV_API_KEY` is read only from the environment. It is not committed, not logged, and stripped from any URL before a URL is saved. Missing key skips Congress.gov and says so in `status.json`.
- Cursor files live in `state/<source>.json`, outside `/docs`, so a rerun can resume. Feeds dedupe by `id`.
- Requests send `CivicTracker-bot/1.0` and wait about a second between calls to the same official host. `efdsearch.senate.gov` is blocked in the client. Senate search automation stays off.
- httpx request logging is set to WARNING so a future run cannot print a URL that contains `DATA_GOV_API_KEY`.
- Bill text on the federal page uses the latest official action as `summary`. CRS summaries are not requested, which avoids one API call per bill.
- Federal Register collection stops at 2,000 hits per date window and splits the dates instead of requesting page 3. Rules and proposed rules are included. Notices are not, so the single JSON file stays a list of rules and orders.
- The committed window is a backfill of 15 Oct 2026–16 Nov 2026 so the recent executive orders are present. A scheduled run with no dates resumes at `completed_through`.
- Federal live check on 16 Nov 2026: 379 rules and proposed rules, 3 executive orders (EO 14436, EO 14437, EO 14438), 9 House roll calls, 6 Senate roll calls. A second run kept the same 397 ids. House roll 323 is "Passed. yeas 392, nays 18" for H.R. 2102, matching the Clerk XML. Senate vote 262 matches the LIS XML. Congress.gov recorded the missing-key skip and made no request.
- Trades live check for filings dated 1–16 Nov 2026: 23 House PTR filings, 134 transaction or scanned-link rows, 0 parse failures after the asset-text fix. Two scanned PDFs (doc ids 9116399 and 9116403) are link-only. Jonathan Jackson's BP row is owner joint, ticker BP, sale (partial), `$1,001 - $15,000`. Richard W. Allen's Sherwin-Williams row is owner spouse. A second run added no ids. Senate list is 100 link rows from senate.gov, including Angela D. Alsobrooks (Democratic, MD). No request was made to efdsearch.senate.gov.

## Open questions

- Pages hosting: this environment cannot enable it. A repo admin still needs to turn on `main` / `/docs`.
- The api.data.gov key is not in this environment. Congress.gov stays skipped until `DATA_GOV_API_KEY` is set as an Actions secret.
