# Daily and seven-day forecast evaluation

September 15, 2026. P2-FR7: one predeclared comparison of the existing baseline
and unchanged recency candidate using the recovered participation data.

## Decision and result

Keep `gm-rates-1` as the working baseline. The existing
`gm-rates-recency-1` remains experimental. Recency worsens skater point error at
both horizons. Its small goalie point-error reductions have paired intervals
that include zero. This does not support replacing the baseline or promoting a
goalie-only variant. No parameters were searched or changed.

The run completed 153,263 paired player/horizon cases across 161 daily and 23
seven-day windows, November 3, 2025 through April 12, 2026. Both models use the
same cases. Fantasy-point metrics cover 151,722 pairs after separate forecast
and scoring-source exclusions.

| Horizon and group | Point-scored cases | Baseline point MAE | Recency point MAE | Recency minus baseline, paired week interval |
| --- | ---: | ---: | ---: | --- |
| Daily skaters | 120,270 | 1.6483 | 1.6584 | +0.0041 to +0.0147 |
| Daily goalies | 12,497 | 2.2693 | 2.2655 | -0.0129 to +0.0043 |
| Seven-day skaters | 17,186 | 7.4919 | 7.6366 | +0.0982 to +0.1913 |
| Seven-day goalies | 1,769 | 9.6278 | 9.5555 | -0.1605 to +0.0021 |

These are errors for total points during the named horizon, including days without
games. They are not directly comparable with the earlier conditional next-game
errors. To make the effect of off days visible, the report also separates cases
with scheduled opportunities according to the pre-cutoff last-known team:

| Horizon and group, scheduled opportunities | Cases | Baseline point MAE | Recency point MAE |
| --- | ---: | ---: | ---: |
| Daily skaters | 50,412 | 3.9298 | 3.9538 |
| Daily goalies | 5,194 | 5.4600 | 5.4508 |
| Seven-day skaters | 15,704 | 8.1989 | 8.3572 |
| Seven-day goalies | 1,613 | 10.5589 | 10.4797 |

Workload is measured independently from scoring:

| Horizon and group | Appearance-count MAE, baseline / recency | Any-appearance Brier, baseline / recency |
| --- | --- | --- |
| Daily skaters | 0.1027 / 0.1038 | 0.05933 / 0.05612 |
| Daily goalies | 0.1855 / 0.1864 | 0.09291 / 0.09271 |
| Seven-day skaters | 0.6491 / 0.6548 | 0.13591 / 0.13485 |
| Seven-day goalies | 0.6490 / 0.6503 | 0.15438 / 0.15738 |

Recency improves skater any-appearance Brier scores but does not improve skater
appearance-count or point MAE. Seven-day goalie any-appearance Brier error worsens;
its paired difference interval is +0.00173 to +0.00436. A gain on one target does
not establish a general model improvement. Detailed calibration bins,
individual-stat errors, signed errors, conditional average scoring-rate errors
and sparse-history groups are retained in the private report.

## What was frozen before the run

The private plan hashes the three normalized histories ending 2024 through 2026,
the scoring configuration, the verified participation ledger and its audit report.
The model formulas remain the existing 730-day rate history with 20 pooled
appearance equivalents, Beta(1,1) workload smoothing, and the candidate's fixed
60-day recency half-life. Workload training uses the newly complete season's
dressed/scratch observations; older incomplete roster cohorts are not mixed in.

The run budget was one model pair, the declared dates and at most 300,000 cases.
It stops after the paired results and coverage checks. No extra candidate,
subgroup promotion or favorable-result search follows this result.

## Prediction cutoffs and outcomes

Each cutoff is 00:00 UTC. Daily windows last one day; Monday cutoffs also produce
a fixed seven-day forecast. These are explicitly named research horizons, not
verified historical Yahoo matchup boundaries.

The forecast cohort contains players listed dressed or scratched in a verified
game within the previous 30 calendar days. Only game UTC dates strictly before
cutoff minus one day enter either membership or training. The latest eligible
observation supplies the last-known team. No appearance, scratch, team change or
scoring result inside the horizon can change the original cohort or forecast.

For each model, expected appearances equal its workload probability multiplied
by the last-known team's scheduled games. Expected scoring statistics precede
application of the league weights. The probability of at least one appearance is
`1 - (1 - p) ** games`, an explicit independent-game approximation. It is distinct
from expected appearance count and does not establish a qualification probability.

Outcomes count the selected player's appearances for any NHL team in the horizon.
A midweek trade can therefore produce an error in the original forecast. A selected
player absent from complete NHL outcome coverage has zero observed appearances;
the reason for the absence is not required. If any NHL game in a window lacks
verified coverage, the whole window is restricted instead of manufacturing zeros.

Scoring conflicts exclude affected point/stat targets while preserving separately
verified participation. A missing rate forecast is unknown, not zero production.
Conditional rate error compares the predicted per-appearance rate with the
observed horizon average when at least one appearance occurred. The multi-day
average can have lower variance than individual games and is labeled accordingly.

## Coverage and limitations

All evaluated windows have complete game coverage. Participation covers every
selected case, including those without a supported scoring rate. Point metrics
exclude 1,500 cases without scoring forecasts and 41 player/horizon cases with
scoring-source conflicts. Daily and weekly exclusions can concern the same
underlying game; these are not 41 distinct damaged game records.

Of 41,081 daily appearing-player windows, 388 involve players outside the
pre-cutoff cohort. For seven-day windows, 377 of 14,556 appearing-player windows
fall outside it. These exclusions include debuts and returns without recent
listed membership. The report does not choose players from future appearances to
improve coverage. It also retains 23 daily skater cases where an appearance
occurred despite no scheduled opportunity for the player's last-known team.

This is a retrospective development comparison on previously inspected seasons.
Final actual schedules and a conservative reporting lag are assumptions, not
archived evidence of what a manager knew then. Later source corrections may
remain. The recent-player cohort does not establish Yahoo ownership, eligibility,
injury status or historical fantasy rosters. Appearance means recorded positive
ice time under the audited definition, not an independent certification of every
official games-played convention.

Paired intervals use 200 calendar-week block bootstrap samples, seed 20260914.
They preserve cases within a week but do not remove dependence across weeks.
Calibration is reported empirically; no calibrated player prediction intervals or
independent predictive superiority are claimed. The result does not measure
real-roster action value or authorize current lineup changes.

## Verification and reproduction

The required unittest suite passes 239 tests. New checks cover hand-calculated
daily/seven-day points, future-data invariance, in-window team changes, missing
game coverage, source conflicts, unsupported rates, reporting lag, stale
membership, deterministic output, duplicate identities and UTC boundaries.

Private evidence under `var/prd-2.0/p2-horizon-evaluation/`:

- `plan.json`: frozen input hashes, formulas, windows, groups and stopping rule.
- `tests.log`: required full-suite result.
- `results/predictions-and-outcomes.jsonl`: paired frozen forecasts and separate outcomes.
- `results/report.json`: metrics, coverage, paired intervals and implementation hashes.
- `artifact-verification.json`: persisted-case arithmetic and independent reference checks.

The evaluator performs no downloads or model promotion:

```sh
uv run python -m research.evaluate_gm_horizons --help
```

Preserve prior outputs. Repeating a completed experiment requires a new decision
or a defect to resolve; this result does not authorize further parameter search.
Prospective frozen forecasts remain the path to an independent promotion claim.
