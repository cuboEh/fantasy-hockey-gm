# Data-source investigation

Checked September 10, 2026. Downloadable historical data and forward projections
are different inputs. No real-player forecast or complete ranking is implemented.

## Yahoo Fantasy

Official API. The developer reports submitting the personal-use read-access
application. Approval is pending. No OAuth app or authenticated request has been
tested. Draft preparation must remain usable without Yahoo integration.

[Access application](https://sports.yahoo.com/developer/access/)

## MoneyPuck

Published downloadable data, permitted for non-commercial use with attribution
under the [download page's guidance](https://moneypuck.com/data.htm). Unlisted
website scraping requires approval. Credit MoneyPuck.com on derived outputs.

Two historical season-summary CSVs were retrieved into ignored dated snapshots:

- [Skaters, season starting 2025](https://moneypuck.com/moneypuck/playerData/seasonSummary/2025/regular/skaters.csv)
- [Goalies, season starting 2025](https://moneypuck.com/moneypuck/playerData/seasonSummary/2025/regular/goalies.csv)

The retrieved skater file has 4,700 rows; the goalie file has 490. Both contain
`all`, `5on5`, `5on4`, `4on5` and `other` situations. Never sum all situations
together: the `all` rows overlap the situation rows. Rows are not unique players.
The skater schema includes goals, primary/secondary assists, shots, hits, expected
goals, ice time and games played. The goalie schema includes goals allowed,
shots on goal and expected goals, but no explicit wins or shutouts. No explicit
skater plus/minus field was found. Each snapshot has a URL, retrieval timestamp,
SHA-256, column list and row count in an adjacent metadata JSON file.

Before building an adapter, verify the data dictionary and situation coverage.
Do not equate 5-on-4 scoring alone with all power-play points or infer official
plus/minus from a simple on-ice goal difference. Validate saves derivation,
season completeness and player identity against another source. MoneyPuck's
positions are not automatically Yahoo eligibility. These are historical inputs,
not next-season projections, and cannot alone supply every required scoring stat.

## Hashtag Hockey

The [projection page](https://hashtaghockey.com/fantasy-hockey-projections)
identifies its projections as 2026-27, updated September 3, 2026. It is a candidate
for research, not an approved ingestion source. Export access and reuse rights
have not been established, and no dataset was scraped or imported.

Verify any supplied file's season, player identities, eligibility, total versus
per-game basis, projected games and goalie counting-stat coverage before use.
The separate [points rankings page](https://hashtaghockey.com/fantasy-hockey-points-league-rankings)
currently labels itself 2025-26; do not mistake it for next-season projections.

## Decision

Keep a normalized offline input boundary. Accept a permitted projection export
once its full field coverage is verified. MoneyPuck can supply supporting
historical features. If a baseline model is built instead, label its assumptions,
obtain missing scoring inputs and validate out of sample. Missing values must
remain explicit; zero-fill would distort player comparisons.
