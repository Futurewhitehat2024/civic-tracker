# Civic Tracker

Nonpartisan static site for federal government actions and congressional stock trades, drawn from official sources. The name above is the placeholder set in `docs/js/config.js` (`name`). Change that one value to rename the site in the header and page titles.

The site is plain HTML, CSS, and vanilla JavaScript. There is no framework and no build step. GitHub Pages should serve the **`/docs`** folder on the `main` branch. The repository root is not the site root.

## Pages

| File | Page |
| --- | --- |
| `docs/index.html` | Home: short intro and links to the feeds |
| `docs/federal.html` | Federal actions (bills, votes, executive orders, Federal Register), with search and type filters |
| `docs/trades.html` | STOCK Act periodic transaction reports, with member, chamber, party, and date filters |
| `docs/status.html` | Per-scraper last run, records collected, and errors |
| `docs/about.html` | Nonpartisan statement, official-sources note, methodology placeholder, AI and data disclaimer |

Shared files: `docs/css/site.css`, `docs/js/config.js` (display name), `docs/js/common.js` (branding, fetch, empty state). Each feed has its own script: `federal.js`, `trades.js`, `status.js`.

## Data

The pages do not embed records. They fetch:

- `docs/data/federal.json`
- `docs/data/trades.json`
- `docs/data/status.json`

Those files are committed empty and valid:

```json
{
  "updated": null,
  "items": []
}
```

When `items` is empty, the feed shows: "No data yet; scrapers not live". Field names for later scrapers are in [`docs/data/SCHEMA.md`](docs/data/SCHEMA.md). This repository does not include scrapers, API keys, or other secrets.

Fetch URLs are relative (`data/federal.json`), so they work on a project site such as `https://<user>.github.io/civic-tracker/` and on a local server.

## Enable GitHub Pages

1. Open the repository **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Branch: **main**. Folder: **/docs**.
4. Save.

After the first deploy, the site is at:

`https://futurewhitehat2024.github.io/civic-tracker/`

`docs/.nojekyll` is present so GitHub Pages will not run the files through Jekyll.

## Local preview

`fetch` does not work from `file://`. From the repository root:

```bash
python3 -m http.server 8000 --directory docs
```

Then open `http://127.0.0.1:8000/`.

## Progress

See [`PROGRESS.md`](PROGRESS.md) for what is done, the next step, decisions, and open questions.
