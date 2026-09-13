# Broad source survey, September 10, 2026

Sources are selected for distinct jobs, not counted as independent votes.
No paid purchase, account creation, Yahoo action or gated-data bypass was made.

| Source | Potential contribution | Result / decision |
| --- | --- | --- |
| [Hockey Insights open data](https://hockeyinsights.ca/opendata/) | Published historical counting lines and IDs | Downloaded the explicitly offered JSON under its stated free-use terms. Used for an auditable baseline. Independent derived source, not an NHL-endorsed service. |
| [MoneyPuck](https://moneypuck.com/data.htm) | Historical chance quality and usage context | Existing permitted downloads joined to the board. Features remain annotations pending validation. |
| [NHL statistics](https://www.nhl.com/stats/) | Official reference and raw counts | Small samples verified earlier; no bulk import. Automated external-use permission remains unresolved. |
| [5V5/DFO projections](https://www.dailyfaceoff.com/tools/nhl-player-projections) | Full projections, provider-reported Yahoo eligibility and ADP | Docs offer export for custom workflows; direct 5V5 browser inspection showed account-gated cells. No gated data imported. Optional user-obtained export. |
| [Hashtag Hockey](https://hashtaghockey.com/fantasy-hockey-projections) | Alternate projections and market context | Current-season page found, reuse/export route still unverified. Research only. |
| [Dobber guide](https://dobbersports.com/product/dobbers-2026-27-fantasy-hockey-guide/) | Projection spreadsheet and deployment research | Paid download candidate; not purchased. Verify complete scoring-field coverage before choosing it. |
| [Apples & Ginos](https://applesandginos.com/) | Independent fantasy analysis/projections | Site reviewed; no directly verified projection export obtained in this pass. |
| [Daily Faceoff line combinations](https://www.dailyfaceoff.com/teams) | Deployment evidence for role scenarios | Research reference. No bulk extraction or automated role claims. |
| [HockeyBangers methodology](https://hockeybangers.com/method) | Explainable skater-model comparison | Research reference; export access not established, goalie coverage needs checking. |
| [Natural Stat Trick](https://www.naturalstattrick.com/) / [HockeyViz](https://hockeyviz.com/) | Further analytical context | Pages failed to load in this research pass. Neither availability nor use permission was established. |

## Data-quality findings

The Hockey Insights catalogue explicitly permits reuse and describes its
limitations. The downloaded flagship file contains 400 skaters, 61 goalies and
six consensus-only entries. Historical rates and source flags are used; its
cross-platform consensus ranks are not ADP and are not used to set player value.
The source is a selected pool rather than a complete fantasy draft universe.

MoneyPuck annotation uses ID and normalized-name checks, season 2025 and only
`situation=all`. In the current board, 452 players match; six identity mismatches
are flagged without attaching features, and three lack matches. Thirty players
have discrepancies in compared raw statistics. Those counts are not averaged;
the baseline retains its input and exposes the conflict for review.

The provider's estimated hits/blocks and small-sample flags stay visible. All 467
players initially have provisional NHL primary positions. A manual, sourced
eligibility correction can replace them. No source can establish Yahoo ownership
or player availability in this specific league while API access is pending.

## Season context

The NHL confirms an 84-game 2026-27 schedule beginning September 29.
[NHL schedule announcement](https://www.nhl.com/news/nhl-stats-pack-2026-27-regular-season-schedule)

Do not carry forward an 82-game projection cap. Yahoo matchup dates remain
league-specific and are not established by the NHL schedule announcement.

## First evaluation diagnostic

Using the current source's complete three-season cases, predict 2025-26 points
per appearance using either 2024-25 alone or a 75%/25% blend of 2024-25/2023-24.
Under the private league weights, mean absolute errors were:

| Group | Cases | Prior-season only | Two-season blend |
| --- | ---: | ---: | ---: |
| Skaters | 370 | 1.118 | 1.100 |
| Goalies | 53 | 2.133 | 1.842 |

This is a retrospective diagnostic, not evidence of a validated forecast. The
player pool was selected after the target season, historical records may include
corrections, and missing histories are excluded. Actual appearance counts are
not predicted here. No comparison to the user's decisions or full roster policy
has been made. Detailed results remain in ignored `var/baseline-diagnostic.json`.

The next data improvement should address a concrete gap: current eligibility,
workload/role assumptions, rookie projections or a verified independent export.
Adding another correlated rating is lower priority.
