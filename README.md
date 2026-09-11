# Fantasy Hockey GM

A private, non-commercial fantasy hockey analytics tool being planned by an individual developer for personal use in one Yahoo Fantasy Hockey league.

## Draft planning and validation update

The [draft planning guide](docs/two-turn-draft-planning.md) documents scenario-aware
`fantasy draft-plan`, pick-now versus next-turn comparisons, starter-only goalie
rates, and an explicit coverage alternative. Across 216 historical drafts, the
new planner did not beat the existing coverage strategy against rank-following
opponents, so it remains optional. Shrunken starter rates reduced historical
rate error by 17%. All 14 seats passed complete draft/recovery rehearsals;
116 tests pass. Current forecasts are frozen for prospective evaluation.

Next: actual draft slot, Yahoo eligibility/rankings, missing rookie projections,
and refreshed high-impact health/role evidence. The guide records remaining
model limitations and reproducible commands. The live draft session is untouched.

## Goalie draft readiness

The [completed goalie review](docs/goalie-review-complete.md) covers all 62 board
goalies: 61 conditional scenarios and one unresolved current job. Use the v2
workload file with the validated 1,344-game calendar and `fantasy goalie-weeks`. Draft-guide review notes are read-only; scenario outputs
do not replace the baseline ranking. See the guide for commands and caveats
about unconfirmed Yahoo matchup boundaries.

## Goalie coverage update

The [weekly goalie coverage fix](docs/goalie-coverage.md) now credits protection
against missed minimums in draft simulations. Across nine seasons, baseline
missed weeks fell from 5.80 to 4.41, with +22 counted FP per season. Coverage
advice is available in `draft-guide --goalie-calendar var/history-2026.json`;
experimental results do not automatically change the live ranking.

## Current pre-draft work

The [pre-draft readiness guide](docs/pre-draft-readiness.md) records the latest audit,
reviewed 14-team tracker, ranking import, all-slot rehearsals and remaining data
gaps. Start with `uv run fantasy draft-guide --db var/draft-14-reviewed.sqlite`.
The board is provisional; Yahoo eligibility and rookie/workload projections still
need review.


## Player-specific contextual pilot, September 10

The first [contextual scenario pilot](docs/contextual-scenarios.md) now separates
reported evidence from analyst parameters for Tkachuk, Barkov, Jarvis and the
Minnesota goalie tandem. It includes staged recovery, stat-specific role changes,
joint goalie starts and separate starter/relief rates. Full private results are
`var/context-pilot-2026-09-10-v3.md`. The current draft board remains unchanged;
these conditional cases are not calibrated forecasts or selected recommendations.
Next: verify deployment/recovery inputs, assess small-sample goalie rates, and
compare useful lineup/IR replacement value before choosing a working projection.

## Learning from historical situations

A [chronological analogue experiment](docs/historical-analogues.md) now tests
whether similar prior workload and scoring trajectories improve later-season
predictions. It evaluates workload-only and workload-plus-rate corrections,
including a pre-season top-224 subset. Dated injury/role labels are not yet
available, so the results do not calibrate surgery-specific recovery or trades.
No variant has replaced the live draft model.

## Analogue draft replay completed, September 10

The [14-team replay](docs/analogue-draft-replay.md) evaluated 270 drafts across
nine seasons. Analogue corrections improved basic point drafting by about 85
counted points, but added only 16 to baseline usable-game drafting, positive in
5/9 season averages and slightly negative excluding shortened seasons. No model
promotion is justified. A key failure involved insufficient weekly goalie
appearances, despite improved average forecast errors.

A four-case historical goalie catalogue now keeps dated preseason labels separate
from observed outcomes. It is an exploratory pilot, not a causal training set.
Next work is weekly goalie-coverage utility and a systematically expanded context
catalogue. The current draft board remains unchanged. All 86 tests pass.

## Project status

Early local development. The developer submitted a Yahoo Fantasy Sports API access application on September 10, 2026; approval is pending. There is no deployed service or Yahoo connection.

The local implementation includes league-specific scoring, explicit skater role scenarios, a real-player historical baseline board, CSV export, and a manual SQLite snake-draft tracker. The baseline is provisional: workloads, rookies and Yahoo eligibility need review. It is not a validated draft strategy.

Start with the [draft-day guide](docs/draft-day.md). See the [broad source survey](docs/source-survey.md), [development instructions](docs/development.md), [data-source investigation](docs/data-sources.md), and [model design](docs/model-design.md).

Next priorities are verified eligibility, documented workload and role adjustments, rookie coverage, and position-specific replacement value. A permitted independent projection export would provide a useful comparison. The current league size is 14 teams; draft slot remains unknown. Historical simulations default to 14 teams, with other sizes available through `--teams`. Yahoo approval is not required for the offline board and tracker.

Historical refinement has started: a [chronological draft experiment](docs/backtesting.md)
compares eight projection/selection variants, locks the tuning-season winner,
and evaluates a later season. Current player-pool bias and the absence of daily
lineup replay prevent treating it as a validated season simulation.

The [first-study audit](docs/first-study-review.md) corrects a confirmed zero-game
outcome. The apparent later-season gain falls from 387 to 85 whole-roster points;
no model is promoted. It also records the route and remaining data gaps for
2015-onward evaluation.

The [evaluation follow-up](docs/replay-and-workload.md) adds a timestamped daily
lineup replay, an experimental historical-usage workload model, stricter missing
outcome checks, and inspected 2015-16 MoneyPuck snapshots. Real historical daily
replay still needs complete source data; these changes are not a validated model
upgrade.

The [six-step historical pipeline](docs/six-step-implementation.md) now covers
2015-16 through 2025-26 with real daily records, four draft policies, separate
streaming replays, hypothetical H2H comparisons and a dated 2024 market sensitivity
run. Source conflicts and historical metadata gaps remain explicit. The live
board has not been replaced by an experimental winner.

## Intended use

The proposed tool will run locally in Python with a command-line interface and SQLite storage. Its intended user base is one person, the developer.

Planned features include league-specific draft preparation, player valuation, schedule and lineup opportunity analysis, and recommendations for roster and streaming decisions. Every recommendation should explain its inputs, assumptions, and tradeoffs.

## Requested Yahoo access

Read-only access to the developer's authorized fantasy league information:

- League settings, scoring weights, and roster positions.
- Team rosters and player position eligibility and status.
- Available players, ownership, and waiver information where supported.
- Standings, matchup scores, and transaction history where supported.

All roster changes will be made manually through Yahoo. No write access is requested, and no browser automation or scraping workaround is planned.

## Data handling

The project proposes to combine league information with permitted hockey schedules and statistics for private analysis, subject to the applicable provider agreements. Any local caching and historical retention will follow those agreements. Yahoo attribution will be included wherever required when Yahoo data is used.

Credentials, account information, league data, and private snapshots will not be published in this repository. There is no planned sale or redistribution of Yahoo data and no public application service.

## Affiliation

This is an independent personal project and is not affiliated with or endorsed by Yahoo or the NHL.
