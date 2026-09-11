# Data-source investigation

Checked September 10, 2026. Downloadable historical data and forward projections
are different inputs. A provisional historical baseline is now implemented;
it is not a complete or validated forecast. See the [expanded survey](source-survey.md).

## SportsDataverse historical releases

Follow-up September 10: published skater/goalie box scores, scoring events and
schedules were downloaded for seasons ending 2013-2026. The adapter and source
conflicts are documented in [the historical pipeline](six-step-implementation.md).
These third-party downloads supply historical research inputs without directly
scraping Yahoo or NHL pages. They do not establish historical Yahoo eligibility.

## Hockey Insights

The [open-data catalogue](https://hockeyinsights.ca/opendata/) explicitly offers
reusable JSON. The adapter consumes historical counting lines and preserves source
flags, then applies local scoring. It does not consume vendor fantasy scores or
consensus ranks. This independent derived dataset supplies the initial baseline;
source conflicts, incomplete player coverage and estimated fields remain visible.

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

## NHL statistics discovery

Follow-up September 10: the [NHL statistics site](https://www.nhl.com/stats/)
provides the official reference. The public JSON
[report configuration](https://api.nhle.com/stats/rest/en/config) was inspected,
followed by three limited, one-row report requests for the regular season with
`seasonId=20252026` and `gameTypeId=2`. No bulk statistics were downloaded or saved.

Base URL: `https://api.nhle.com/stats/rest/en/`

| Report | Scoring fields observed in a returned sample row |
| --- | --- |
| `skater/summary` | `goals`, `assists`, `plusMinus`, `ppPoints`, `shots` |
| `skater/realtime` | `hits` |
| `goalie/summary` | `wins`, `goalsAgainst`, `saves`, `shutouts` |

All samples include `playerId` and `seasonId`. Requests used `isAggregate=false`,
`isGame=false`, `start=0`, `limit=1`, and the season/game-type filter above.
Summary and realtime reports returned different first players: joining by row
order would be wrong. The report name `realtime` is not a measured freshness SLA.

Classification: first-party public web-data endpoints, not a verified supported
third-party developer API. Technical reachability and field names are verified;
bulk reuse permission, stability, full coverage and freshness are not. NHL terms
restrict unauthorized automated collection. [Terms](https://www.nhl.com/info/terms-of-service)

An offline normalizer can use this schema while the acquisition route is settled.
If authorized direct retrieval is unavailable, use a permitted export or licensed
provider offering these fields. Do not label accessibility as permission.

The samples establish a promising route to all required raw scoring fields.
They do not establish Yahoo-specific eligibility or official fantasy corrections,
and no NHL adapter or complete season import has been implemented yet.

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

The user prefers a multi-source approach: recorded NHL production, MoneyPuck
analytical features and our own tested fantasy model. An external projection
export is an optional baseline or blend component, not a required architecture.
See [model design](model-design.md).
