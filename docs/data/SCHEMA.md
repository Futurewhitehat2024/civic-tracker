# Feed JSON schema

The static site reads the original three feed files. Scrapers also write package files used by the data-based GovWatcher tiers. Overwrite files in place. Do not commit API keys or credentials next to them. Congressional stock-trade filings in `trades.json` stay out of every package export.

Schema version `1.1.0` adds optional package fields (`tags`, `jurisdiction`, `commentsCloseOn`, `effectiveOn`, `agencies`) and the derived files listed at the end of this document.

Each file is a JSON object:

| Field | Type | Meaning |
| --- | --- | --- |
| `updated` | string or `null` | ISO 8601 timestamp of the last successful write, or `null` if a scraper has never written the file. |
| `items` | array | Records. An empty array is valid and means there is nothing to show. |

Empty files committed in git:

```json
{
  "updated": null,
  "items": []
}
```

Dates inside items are ISO 8601 (`YYYY-MM-DD` or a full timestamp). URLs are absolute `http` or `https` links to the official record. The pages render text with `textContent` and only link URLs whose protocol is `http` or `https`.

## `federal.json`

Government actions: bills, floor votes, executive orders, and Federal Register documents.

Item fields:

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `id` | yes | string | Stable id from the source, unique within the file. |
| `kind` | yes | string | One of `bill`, `vote`, `executive_order`, `federal_register`. |
| `title` | yes | string | Official title or short description. |
| `date` | yes | string | Action, vote, signing, or publication date. |
| `url` | yes | string | Official source page. |
| `source` | yes | string | Short source label, such as `Congress.gov` or `Federal Register`. |
| `summary` | no | string or `null` | Plain-text summary. Omit or `null` when the source has none. |
| `identifier` | no | string or `null` | Bill number, vote number, executive-order number, or Federal Register document number. |
| `chamber` | no | string or `null` | `house`, `senate`, or `null` for executive and register items. |
| `documentType` | no | string or `null` | Federal Register label such as `Rule`, `Proposed Rule`, `Notice`, `Executive Order`, or `Proclamation`. `null` for bills and votes. Notices live in `federal-notices.json`, which uses this same item shape. |
| `tags` | no | array of strings | Sorted slugs. Federal Register documents and executive orders may be tagged `tariff`, `section-232`, `section-301`, `ieepa`, `hts`, `ustr`, `ita`, `cbp`, `usitc`, or `bis`. Bills and votes use `[]`. |
| `jurisdiction` | no | object | `{ "level": "federal" \| "state" \| "county", "state": "FL" or null, "countyFips": "12021" or null }`. Federal records use `level: "federal"`. |
| `commentsCloseOn` | no | string or `null` | Federal Register `comments_close_on` date. Present after a live scrape or a successful backfill. Omitted on older rows until then. |
| `effectiveOn` | no | string or `null` | Federal Register `effective_on` date. Same presence rule as `commentsCloseOn`. |
| `agencies` | no | array of strings or `null` | Official issuing-agency names from the Federal Register. |

Example item (not committed as data):

```json
{
  "id": "hr-1-119",
  "kind": "bill",
  "title": "Example Act",
  "date": "2026-01-15",
  "url": "https://www.congress.gov/bill/119th-congress/house-bill/1",
  "source": "Congress.gov",
  "summary": null,
  "identifier": "H.R. 1",
  "chamber": "house"
}
```

## `trades.json`

STOCK Act periodic transaction reports, one item per reported transaction. The trades page turns these fields into a short news-style line and links `url`.

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `id` | yes | string | Stable id, unique within the file. |
| `member` | yes | string | Member name as on the filing. |
| `chamber` | yes | string | `house` or `senate`. |
| `transactionType` | yes | string | `purchase`, `sale`, `exchange`, or another label copied from the filing. |
| `asset` | yes | string | Asset description as filed. |
| `amountRange` | yes | string | Amount range as filed, not a computed dollar value. |
| `filingDate` | yes | string | Date the periodic transaction report was filed. |
| `url` | yes | string | Official filing or clerk page for that report. |
| `party` | no | string or `null` | `Democratic`, `Republican`, `Independent`, or another label as reported. `D`, `R`, and `I` are accepted by the page filter. |
| `state` | no | string or `null` | Postal abbreviation. |
| `ticker` | no | string or `null` | Ticker when the filing gives one. |
| `transactionDate` | no | string or `null` | Transaction date when the filing gives one. |
| `owner` | no | string or `null` | `self`, `spouse`, `dependent`, `joint`, or another label copied from the filing. |

Example item (not committed as data):

```json
{
  "id": "ptr-example-1",
  "member": "Jane Q. Public",
  "chamber": "house",
  "party": "Democratic",
  "state": "CA",
  "transactionType": "purchase",
  "asset": "Example Corp",
  "ticker": "EX",
  "amountRange": "$1,001 - $15,000",
  "transactionDate": "2026-02-01",
  "filingDate": "2026-02-20",
  "owner": "self",
  "url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/example.pdf"
}
```

## `status.json`

One item per scraper.

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `id` | yes | string | Stable scraper id, for example `congress-bills`. |
| `name` | yes | string | Short label shown on the status page. |
| `lastRun` | yes | string or `null` | ISO 8601 time the scraper last finished, or `null` if it has never finished. |
| `records` | yes | number | Records collected on the last run. Use `0` when there were none. |
| `errors` | yes | array of strings | Error messages from the last run. Use `[]` when the run was clean. |

Example item (not committed as data):

```json
{
  "id": "congress-bills",
  "name": "Congress.gov bills",
  "lastRun": "2026-03-01T12:00:00Z",
  "records": 40,
  "errors": []
}
```


## Package files (schema 1.1.0)

These files support the data-based packages. They are rewritten at the end of each scraper run, including `--finalize-only`. `trades.json` is never copied into them.

### `deadlines.json` and `deadlines.ics`

One item per comment deadline or effective date found on Federal Register records in `federal.json` and `federal-notices.json`.

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `id` | yes | string | `{recordId}-comment-due` or `{recordId}-effective`. |
| `recordId` | yes | string | The federal or notice record id. |
| `kind` | yes | string | `comment_due` or `effective`. |
| `date` | yes | string | The deadline or effective date. |
| `title` | yes | string | Prefixes the source title with `Comment due:` or `Effective date:`. |
| `url` | yes | string | Official Federal Register page. |
| `source` | yes | string | Usually `Federal Register`. |
| `documentType` | no | string or `null` | Copied from the source record. |
| `tags` | no | array of strings | Copied from the source record. |
| `jurisdiction` | no | object | Copied from the source record. |

`deadlines.ics` is a deterministic iCalendar file of the same items, for calendar import.

### `coverage.json`

Florida county registry used for county packs and per-state pricing. Adjacency comes from the U.S. Census Bureau County Adjacency File. Collier (`12021`) and Lee (`12071`) are `in_test`. The other 65 Florida counties are `planned`. A county pack is the home county plus its Florida neighbors (`pack`).

### `counties.json`

County meeting records, same item shape as `federal.json` except `kind` is `meeting` and `jurisdiction.level` is `county`. Collier and Lee collectors read the official CivicClerk public Events API and are opt-in (`--sources counties`). They are not part of the default `all` group until a county is marked live.

### `manifest.json` and `v1/`

`manifest.json` lists each package dataset, its count, `lastUpdated`, `schemaVersion`, and paths to the versioned JSON and CSV copies under `docs/data/v1/`. The manifest also records that `trades` is excluded from the package API.

### Not collected by the scraper

The influencer referral program is a site and billing feature. Official public data-breach notice sources are documented in [`PLANNED-SOURCES.md`](PLANNED-SOURCES.md). There is no live breach collector yet.
