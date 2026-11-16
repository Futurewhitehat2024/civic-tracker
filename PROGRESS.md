# Progress

## Done

- Chose `/docs` as the GitHub Pages root.
- Added empty, schema-valid `docs/data/federal.json`, `trades.json`, and `status.json`.
- Documented the item schema in `docs/data/SCHEMA.md`.
- Added the display name as the single `name` value in `docs/js/config.js`, plus shared CSS and a small shared script.
- Added home (`docs/index.html`) and about (`docs/about.html`).

## In progress

Federal, trades, and status pages are not written yet.

## Next step

Add the federal actions feed with filter and search stubs that read `data/federal.json`.

## Decisions

- Plain HTML, CSS, and vanilla JS. No framework and no build step.
- Site files live in `/docs` so Pages can serve `main` / `/docs`. A `.nojekyll` file disables Jekyll processing.
- Feeds fetch relative `data/*.json` URLs so the same files work on a project-pages subpath and on a local static server.
- Empty feeds stay empty. No sample records in the JSON files. Example objects live only in the schema doc.
- The visible site name is read from `docs/js/config.js` so a rename does not require editing each page.

## Open questions

- Whether GitHub Pages can be turned on from this environment (needs repo admin on `main` / `/docs`).
- Which official endpoints the later scrapers will use, and how often they should run. Out of scope until scrapers are added.
