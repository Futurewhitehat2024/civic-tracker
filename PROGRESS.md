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

## In progress

GitHub Pages is still off. Creating the Pages site returned 403, "Resource not accessible by integration". The token used here is not a repo admin.

## Next step

A person with admin on the repo turns on Pages: Settings → Pages → Deploy from a branch → `main` → `/docs`. The site should then be at `https://futurewhitehat2024.github.io/civic-tracker/`.

## Decisions

- Plain HTML, CSS, and vanilla JS. No framework and no build step.
- Site files live in `/docs` so Pages can serve `main` / `/docs`. A `.nojekyll` file disables Jekyll processing.
- Feeds fetch relative `data/*.json` URLs so the same files work on a project-pages subpath and on a local static server.
- Empty feeds stay empty. No sample records in the JSON files. Example objects live only in the schema doc.
- The visible site name is read from `docs/js/config.js` so a rename does not require editing each page.
- Filter controls run in the browser on the fetched JSON. They are usable once scrapers fill the files. There is no separate filter API.
- Trade headlines are built in `docs/js/trades.js` from the item fields. The JSON stores the filing fields, not a prewritten sentence.
- Links are rendered only for absolute `http` and `https` URLs.

## Open questions

- Pages hosting: this environment cannot enable it. A repo admin still needs to turn on `main` / `/docs`.
- Which official endpoints the later scrapers will use, and how often they should run. Out of scope until scrapers are added.
