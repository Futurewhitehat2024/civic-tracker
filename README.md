# TheGovWatcher

Nonpartisan static site for federal government actions and congressional stock trades, drawn from official sources. The public name is set in `docs/js/config.js` (`name`). Change that one value to rename the site in the header and page titles.

The site is plain HTML, CSS, and vanilla JavaScript. There is no framework and no build step. GitHub Pages should serve the **`/docs`** folder on the `main` branch. The repository root is not the site root.

## Pages

| File | Page |
| --- | --- |
| `docs/index.html` | Home: what the site tracks, counts, last updated, and latest records |
| `docs/federal.html` | Federal actions, with search, filters, sorting, and a link to the official record |
| `docs/trades.html` | Congressional trade disclosures, with search, filters, and sorting |
| `docs/status.html` | Redirects to the home page. It is not linked from the public site. |
| `docs/about.html` | Purpose, sources, what is shown, update schedule, and disclaimer |

Shared files: `docs/css/site.css`, `docs/js/config.js` (display name), `docs/js/common.js` (branding, fetch, dates). `federal.js`, `trades.js`, and `home.js` load the public records. `status.js` only sends `/status.html` back to the home page.

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

When `items` is empty, a page says that no records are posted yet. Field names are in [`docs/data/SCHEMA.md`](docs/data/SCHEMA.md). API keys are not stored in the repository.

## Scrapers

Python 3.12. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m scrapers --sources all
```

`--sources` accepts `all`, `federal`, `trades`, or a comma-separated list such as `house-ptr,senate-efd`. `--from YYYY-MM-DD` and `--to YYYY-MM-DD` request a backfill. With no dates, each source continues from `state/<source>.json`, or the last 14 days when that file has no cursor.

Congress.gov bills run only when `DATA_GOV_API_KEY` is set in the environment. The value is not printed and is not written into the JSON. If it is missing, `docs/data/status.json` says the source was skipped.

House electronic transaction reports are parsed from the PDF text. Scanned PDFs stay link-only. Senate rows link to the eFD search and do not download filings. See [`SENATE-EFD.md`](SENATE-EFD.md).

Requests identify themselves as `CivicTracker-bot/1.0` and pause between calls to the same host. The client refuses `efdsearch.senate.gov`.

## Scheduled run

`.github/workflows/scrape.yml` runs every day at 11:00 UTC (06:00 EST, 07:00 EDT). That run uses each source's saved cursor. GitHub only runs the schedule from the default branch, so it starts after this workflow is on `main`.

Actions → Scrape → Run workflow accepts:

- `sources`: `all`, `federal`, `trades`, or a comma-separated list
- `from_date` and `to_date`: `YYYY-MM-DD` backfill. Leave both empty for the normal cursor run.

Add the repository secret `DATA_GOV_API_KEY` for Congress.gov bills. The workflow passes it as an environment variable and the scraper does not print it. Without the secret, that source is skipped and `status.json` says so.

The workflow commits updated JSON and `state/` as `github-actions[bot]`. It does not turn on GitHub Pages.

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
