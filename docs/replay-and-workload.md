# Acting on the first-study concerns

Historical note: subsequent implementation now connects real daily records and
verifies the goalie penalty. See [the six-step pipeline](six-step-implementation.md)
for current status; the initial limits below describe the earlier slice.

## Daily usable points

A new offline replay API separates `plan_days` from `settle`. The first receives
only timestamped forecasts, eligibility and schedules. It uses exact maximum
expected-point assignment across active roster positions, including flexible
eligibility. The second receives recorded daily outcomes after selections are
fixed. Bench points are reported separately and never added to lineup points.

```sh
uv run python -m fantasy_hockey.replay \
  --decisions examples/replay/decisions.json \
  --outcomes examples/replay/outcomes.json --config config.example.toml \
  --goalie-minimum 0 --output var/replay-example.json
```

These examples are fictional and do not represent a historical season. For the
private league, use its configuration and a goalie minimum of 3. Decision packets
must specify league week, local lock timestamp with timezone, evidence timestamps,
player IDs, positions, expected points, scheduled status and source. Outcomes
specify date, ID, appearance status, raw scoring statistics and source. A forecast
must include start/appearance uncertainty in expected points; this version does
not infer it. Timestamp claims still need independent source verification.

A missed game requires an explicit sourced nonappearance record. Missing scheduled
player outcomes invalidate weekly totals. Selected goalie appearances count
toward the supplied minimum. Failed minimums leave rule-qualified points unset,
because Yahoo penalty semantics have not been verified. The lineup policy can
bench a negative-expectation goalie; it does not yet optimize that choice against
the minimum requirement or future start opportunities.

This is fixed-roster, one global lock per day. It rejects roster membership
changes. It does not emulate Yahoo per-player locks, acquisitions, waivers or
opponent H2H matchups. No full real-data season replay is claimed. Its useful
boundary is now testable: future outcomes cannot choose the starters.

## Workload estimation

`Model(..., workload_mode='cohort')` adds an experimental alternative to the
fixed 70-skater/45-goalie appearance targets. It finds the five nearest historical
usage transitions for the same player type, excluding the target player, using
only pre-draft seasons. The median following-season appearances becomes the
regression target. Fewer than three transitions means no workload regression.
Only adjacent seasons form a transition.

The model uses appearances, not starts, and lacks team workload allocation, dated
injury context and explicit starter/backup labels. It remains restricted to the
current 82-game historical experiment; shortened-season normalization and an
older complete-history adapter are still needed. It is not promoted to the live
board or added to the old tuning grid after seeing later outcomes.

A development evaluation on the already-inspected 2025-26 season, with the
verified Barkov zero-game correction, gave +26.4 whole-roster points on average
over 125 comparisons. The original fixed-workload candidate gave +84.7. These
small, biased results do not demonstrate superiority of either model. Saved
private reports are `var/cohort-development-study.json` and its audit companion.

## Incomplete-data safeguards

The historical selector now refuses to choose a model if any tuning scenario
lacks complete paired outcomes. Later evaluation's primary mean is unset unless
all comparisons are complete; complete-case means are labeled diagnostic only.
The original reports are retained for provenance, with the sourced outcome audit
preserving the correction path. Older target years now fail explicitly instead
of silently filtering against the three-season source adapter.

## 2015 history acquisition

Two published [MoneyPuck downloads](https://moneypuck.com/data.htm) were retrieved
for 2015-16 and stored in ignored dated snapshots, with URL, timestamp and hash:

- Skaters: 4,490 situation rows, 898 unique all-situation players.
- Goalies: 460 situation rows, 92 unique all-situation players.

The schema has production and usage features, but no explicit skater plus/minus,
goalie wins or shutouts. Full PPP situation coverage also needs verification.
These files are analytical inputs, not a complete fantasy scoring source. Do
not infer an official plus/minus value from on-ice goal differential, or silently
set missing scoring categories to zero. Coverage is recorded locally in
`var/history-2015-coverage.json`. Credit MoneyPuck.com for these inputs.

## Remaining work

Complete raw daily stats and pre-draft player pools/eligibility still block an
honest 2015-onward season replay. Historical ADP has not been acquired, so draft
opponents remain synthetic and the model cannot claim real-market bargains.
The next integration should supply these data to the replay boundary, then add
weekly goalie-aware planning and transaction policies with verified Yahoo rules.
No result here is a forecast of H2H win probability.
