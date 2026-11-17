# Senate eFD

The Senate electronic financial disclosure search at `efdsearch.senate.gov` asks each user to accept a terms agreement before any search. That automation is not approved.

This repository does not request `efdsearch.senate.gov`. The HTTP client rejects that host. Senator rows in `docs/data/trades.json` use transaction type `senate-efd-search` and link to `https://efdsearch.senate.gov/search/`. They are not parsed transactions. Names, parties, and states come from the public Senate contact list at senate.gov.

Do not fetch or submit the eFD search until a legal review that allows it is recorded in this file.
