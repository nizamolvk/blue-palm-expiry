# Data issues

Reviewed against 1 December 2026 (2026-12-01). An expiry before that date is a real expiry, not a data error.

Source file: `data/blue_palm_expiry_items.csv` (56 data rows).
Clean file: `clean_items.csv` (53 data rows). 3 later exact-duplicate copies were removed.

`needs_review` is `yes` when a row still has a problem a person must decide. `review_reason` lists those problems, separated by semicolons. Safe fixes on those rows are already applied where noted below.

## Fixed

### Exact duplicates removed

The later identical copy was removed. The earlier row was kept.

- `BP-1017`: kept line 16, removed line 22.
- `BP-1026`: kept line 20, removed line 41.
- `BP-1004`: kept line 38, removed line 52.

### Dates standardised

Written as `YYYY-MM-DD`. Only values with one valid calendar reading were changed.

- `BP-1022` line 5: `06 Dec 2026` → `2026-12-06`.
- `BP-1008` line 14: `01 Jan 2027` → `2027-01-01`.
- `BP-1015` line 39: `30/04/2027` → `2027-04-30` (30 cannot be a month).

### Branch spelling

- `BP-1019` line 18: branch `Colmbo` → `Colombo`.
- `BP-1030` line 31: branch `DUBAI` → `Dubai`.
- `BP-1005` line 43: branch `colombo ` → `Colombo`.

Rows whose item name or email points at the other city are still listed under needs human review. The branch was not switched.

### Personal information redacted

Passport numbers and phone numbers in notes were replaced with `[REDACTED]`. The values are not repeated here.

- `BP-1039` line 27: passport number and phone number in notes replaced with `[REDACTED]` (value not repeated).
- `BP-1007` line 34: passport number in notes replaced with `[REDACTED]` (value not repeated).

## Needs human review

### Same id, different values

- `BP-1020` was not merged. Line 32 expires `2027-11-13` (note: Renewed early?); Line 57 expires `2026-11-13`.

### Dates cleared or still blank

- `BP-1010` line 13: expiry date is blank.
- `BP-1027` line 42: expiry date `TBC` is not a date, so it was cleared.
- `BP-1003` line 53: `08/12/2026` could be day/month/year or month/day/year, so it was cleared.

### Branch left unresolved

- `BP-1019` line 18: branch was standardised to `Colombo`, but the item name says Dubai, and this email belongs to Dubai on the other consistent rows. The branch was not switched.
- `BP-1030` line 31: branch was standardised to `Dubai`, but the item name says Colombo, and this email belongs to Colombo on the other consistent rows. The branch was not switched.
- `BP-1005` line 43: branch was standardised to `Colombo`, but the item name says Dubai, and this email belongs to Dubai on the other consistent rows. The branch was not switched.

### Emails cleared

- `BP-1033` line 17: email `omar.k bluepalm.example` has a space where `@` would be. A likely address is `omar.k@bluepalm.example`. The clean file leaves the email empty.
- `BP-1014` line 33: email `shanika.r@bluepalm` has no domain suffix. `.example` was not added, and the email was cleared.

### Costs left as written

- `BP-1012` line 26: annual cost is `-450`.
- `BP-1045` line 35: annual cost is `0` (free versus missing is unclear).
- `BP-1005` line 43: annual cost is `0` (free versus missing is unclear).

## Not treated as data errors

- `licence` in `Trade licence` is consistent British spelling.
- The number in `item_name` matches `item_id` (`BP-1000` is `#1`).
- Expiry dates before 1 December 2026 were left as real expiries.
