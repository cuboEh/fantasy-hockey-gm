# Participation data audit

September 15, 2026. P2-FR7, authorized one-time raw-record audit and source pilot.
This is data validation, not a new forecast experiment or a model promotion.

## Decision and acceptance

Determine whether existing raw records and a bounded game-roster sample can
supply participation outcomes for subsequent daily/matchup evaluation. Reuse
saved downloads, preserve their hashes, and keep external fetching separate from
pure reconciliation. Check game/player/team identities, duplicates, ice-time
units, starter labels, dressed players, scratches and unused backups.

The private plan is `var/prd-2.0/p2-participation-audit/plan.json`. It covers one
local audit, 30 deterministic regular-season games and expansion to one season
after the participation checks pass. The sample includes opening games, relief
appearances and observed team changes. It is a source-validation sample, not a
representative forecast test set. No model parameters or rankings change.

## Existing-record results

The audit checked 70 saved CSVs across seasons ending 2013 through 2026 against
their download receipts and joined against 14 saved normalized histories. It
covered 16,692 regular-season games and recovered 667,586 exposure records:

| Observed role | Records |
| --- | ---: |
| Skater with positive ice time | 600,796 |
| Listed skater with zero ice time | 25 |
| Starting goalie | 33,384 |
| Relief goalie | 2,340 |
| Listed goalie with zero ice time and no appearance evidence | 31,041 |

All validated team-games have one starting goalie. Starter serialization switches
between uppercase and lowercase booleans across source releases; both are parsed
explicitly. Ice time is recovered in seconds. No missing player rows are added.

Three goalie records with zero ice time but other appearance evidence are excluded
from this exposure ledger. Another 88 goalie lines have inconsistent shot totals;
positive ice time still supports participation, but their scoring targets must
remain excluded until the conflicts are resolved. This separates field quality
instead of discarding supported workload or accepting contradictory scoring.

Older combined player/team files lack game identity columns and cannot be joined
by row order. The 2018 and 2019 combined player files are byte-identical, as are
their team files. The dedicated skater/goalie files retain game identities; the
audit uses those and does not repair or replace any saved release. Recent team
totals also show 282 goal-total and 30 shot-total discrepancies against skater
sums. Shootout-winning goals can explain some goal-total differences, but the
audit does not assume that every discrepancy has that explanation.

Evidence: `raw-audit-v3/report.json` and `exposure-outcomes.jsonl` under the private
audit directory. Earlier failed/strict-parser passes remain there as development
evidence; v3 is the completed raw audit. No previously saved source changed.

## Source pilot

All 30 games reconcile between saved dedicated boxes, the SportsDataverse raw
game archive and official NHL playing-roster reports. They yield 1,367 records:
1,080 skater appearances, 60 goalie starts, 12 relief appearances, 48 unused
listed goalies and 167 scratches. Two scoring-stat conflicts remain flagged.

Official reports do not expose player IDs in the player table. Dressed players
join by game, team and unique jersey, with position and full name corroboration.
Full-name/nickname differences require explicit reviewed aliases, scoped to
game/team/player. Scratch IDs come from the raw game source's team-specific
scratch list. Ambiguous names are rejected; reviewed variants additionally use
same-season team/jersey/player-ID evidence. No fuzzy name matching is accepted.
The pilot required 27 contextual reviews covering 13 distinct name variants.

Sources: [SportsDataverse raw game archive](https://github.com/sportsdataverse/fastRhockey-nhl-raw)
and [an official NHL playing-roster report](https://www.nhl.com/scores/htmlreports/20252026/RO020001.HTM).
Downloaded records and identity-review details remain private. Cache receipts
retain URL, retrieval time and content hash. Access-denied or rate-limit responses
suspend further uncached requests, without a browser workaround.

Evidence: `pilot/selection.json`, `pilot/fetch-results.json`,
`identity-reviews.json`, and `pilot-final/report.json`. The latter supports the
authorized one-season expansion; expansion results are a separate milestone.

## What these records establish

An appearance prediction can be scored without knowing why a player did not play.
It needs a player chosen for prediction beforehand and complete outcome coverage.
Scratches and unused backups help establish outcomes, but the post-game list must
not select the player population for a purported pregame evaluation.

Historical roster reports cannot establish when an injury, trade or starter
announcement became known. Every recovered row therefore has unknown pregame
availability and an explicit historical-outcome role. They do not update the
current league workspace or imply that its present lineup inputs are complete.

After source reconciliation, define daily and matchup player cohorts using only
information available at the prediction cutoff. Score both models on the same
cases, with separate participation and scoring-target coverage. Previously
inspected seasons support labeled retrospective development evaluation; genuinely
untouched or prospective outcomes are required for an independent promotion claim.
Collect dated player lists and forecasts before games for that prospective study.

## Reproduction and verification

Use new output directories to preserve existing evidence:

```sh
uv run python -m research.audit_participation_records --help
uv run python -m research.fetch_participation_pilot --help
uv run python -m research.validate_participation_pilot --help
```

The validator accepts explicit private `--identity-reviews`; source hashes for
those reviews are checked before use. Failed identities exclude the whole game
from its verified participation ledger. Statistical conflicts remain attached to
otherwise supported exposure records.

The full unittest suite passes 229 tests, including duplicate identities, missing
game IDs, wrong-season releases, corrupted receipts, wrong report dates,
contradictory zero-time records, scoped alias reviews and scoring/workload quality
separation. Evidence: `var/prd-2.0/p2-participation-audit/tests.log`.
