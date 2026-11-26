# Planned sources and package notes

Research for data the GovWatcher packages will need later. Nothing here signs up for a paid API, posts, or markets a feed as live.

## County meetings (in test)

Collier and Lee have official CivicClerk public APIs, so collector stubs exist and can be run with `--sources counties`. They are not in the default scheduled `all` group yet.

| County | FIPS | Status | Official sources |
| --- | --- | --- | --- |
| Collier, FL | 12021 | in_test | CivicClerk Events API `https://colliercofl.api.civicclerk.com/v1/Events`; public portal `https://colliercofl.portal.civicclerk.com/`; legacy IQM2 calendar RSS `https://colliercountyfl.iqm2.com/Services/RSS.aspx?Feed=Calendar` (CivicClerk is the current portal). |
| Lee, FL | 12071 | in_test | CivicClerk Events API `https://leecofl.api.civicclerk.com/v1/Events`; public portal `https://leecofl.portal.civicclerk.com/`. No official Legistar or county-board RSS was found. |

The remaining 65 Florida counties are listed as `planned` in `coverage.json`, with Census adjacency used for county packs. A county should be marketed only after its status is `live`.

## Data-breach notices (not collected yet)

The packages call for breach notices in every tier once a live feed exists. These are official public lists. None is a documented, terms-clear, machine-readable government API, so there is no collector on this branch.

| Source | Official page | Notes |
| --- | --- | --- |
| California Attorney General | https://oag.ca.gov/privacy/databreach/list | Public HTML list of sample notices sent to the AG when more than 500 California residents are affected. |
| Washington Attorney General | https://www.atg.wa.gov/data-breach-notifications | Public HTML directory of notices filed under RCW 19.255 and RCW 42.56.590. |
| Oregon Department of Justice | https://justice.oregon.gov/consumer/DataBreach | Public HTML list of sample notices sent when more than 250 Oregon consumers are affected. |
| Maine Attorney General | https://www.maine.gov/ag/consumer/identity_theft/ | Public reports have lived in the AG's viewer; the list interface has been unreliable. Confirm the current official page before collecting. |
| Texas Attorney General | https://oag.my.site.com/datasecuritybreachreport/DataSecurityReportsPage | Public Salesforce-hosted report table. Not a documented bulk API. |
| Florida | — | No public statewide data-breach notice list was found. |
| HHS Office for Civil Rights | https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf | Official federal HIPAA breach portal (JavaScript application). Review terms before any collector. |

A later collector should use an official bulk file or documented API, identify itself as `CivicTracker-bot/1.0`, and stay out of any source whose terms do not allow automated collection.

## Influencer program

This is a site and billing feature (referral accounts, tracked signups, and payouts). The scraper does not collect it and does not need a source.

## Congressional stock trades

`trades.json` remains on the free public news page only. It is not tagged for packages, not written into `manifest.json` datasets, and not copied into the `v1/` bulk export.
