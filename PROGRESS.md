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

## In progress

README still describes only the placeholder project.

## Next step

Replace the README with the site layout and Pages instructions. A local browser check of the five pages already passed, including empty states, nav, and filters against intercepted sample JSON (that sample is not committed).

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

- Whether GitHub Pages can be turned on from this environment (needs repo admin on `main` / `/docs`).
- Which official endpoints the later scrapers will use, and how often they should run. Out of scope until scrapers are added.
