# Learning from historical situations

The first analogue model learns corrections from past workload and scoring
trajectories. It does not yet learn surgery-specific recovery or the causal
impact of an offseason trade, because those dated historical labels are absent.

For every target season, candidate features use only the preceding three
completed seasons. Features are recent appearances, fantasy points per
appearance, changes in those two values, an observed prior-season team-change
flag, missing-year gap and single-season-history flag. Forwards, defensemen and
goalies have separate comparison pools. The query player is excluded from its
own historical neighbors.

The model finds up to 40 similar historical cases whose outcome seasons finished
before the target season. It estimates their baseline prediction errors and
shrinks the mean correction toward zero with 40 prior observations. Fewer than
ten neighbors means baseline fallback. Rate corrections require at least ten
neighbors with 20 or more normalized appearances in the outcome season. These
settings were fixed for this experiment, not selected by searching its results.

Two variants are compared with the same historical baseline: workload correction
alone and workload plus rate correction. Neither is promoted automatically.
The baseline uses three available seasons with normalized geometric 1, 1/3, 1/9
weights. This differs from the live board's 60/30/10 weighting, so current analogue
estimates are research outputs rather than direct replacements for live values.

## Chronological evaluation

Fourteen source seasons ending 2013-2026 supply historical data. Analogue training
outcomes start with 2015-16; evaluation covers nine seasons, 2017-18 through
2025-26. Each evaluation season gets a new training pool containing only earlier
outcomes. Historical input hashes and source-conflict counts accompany the report.

Mean absolute point error is reported separately for F/D/G, averaged equally
across seasons. A second evaluation uses each year's top 224 players by preseason
baseline points, selected without outcomes. That subset is useful for draft
relevance, but does not represent a roster-constrained draft or actual Yahoo ADP.

```sh
uv run python research/test_historical_analogues.py --history-dir var \
  --output var/NEW-analogue-study.json
```

Private report: `var/analogue-study-2026-09-10-v2.md`. It includes current nearest
historical comparisons for the contextual pilot players. Nearest numerical
trajectories do not establish comparable injuries, roles, ages or circumstances.

## Limits and next use

All games and points use 82-game equivalents, with each player's last observed
team schedule as the normalization denominator. Shortened seasons and traded
players therefore introduce approximation. Missing outcome players count as
zero NHL production under the assumption of complete source coverage, which
includes retirement and departures, not only injury. Source disagreements remain.

The model observes in-season team changes before the draft, not an offseason move
inferred from a player's first game after the draft. That distinction prevents
future team assignments from leaking into the features.

Before historical cases can calibrate the contextual scenarios, build a dated
case catalogue: known transaction date, pre-draft expected deployment, prior role,
confirmed injury/recovery status and what actually happened afterward. Label
missing information explicitly. Keep projected role changes separate from observed
role changes. Then test whether those features improve errors and interval
coverage on later seasons, not merely whether they tell a plausible story.

Current work tests average forecast error. It does not produce calibrated
probabilities or prediction intervals. Repeated player histories are correlated;
researchers have already inspected these seasons, so chronological evaluation
is not a claim of a pristine holdout. Lineup usefulness and draft outcomes still
need a separate replay comparison for any variant worth advancing.

## First results

12,107 player-season forecasts were evaluated. The draft-relevant subset contains 224 preseason point-ranked players per season, 2,016 cases in total.

| Group | Baseline MAE | Workload + rate MAE | Error reduction | Improved seasons |
| --- | ---: | ---: | ---: | ---: |
| F | 134.6 | 128.5 | 4.5% | 9/9 |
| D | 119.5 | 112.4 | 5.9% | 9/9 |
| G | 174.4 | 152.2 | 12.7% | 9/9 |

The unrestricted pool improved roughly 8-9%. Draft-relevant results above are the more useful screening measure. Forecast-error reductions do not establish roster value, category wins, or a better draft. The additional rate correction contributes less than the workload correction overall. No parameters were retuned after these results.

All 82 tests pass. Tests check that future seasons cannot alter candidate features, future outcomes and the query player cannot enter its neighbor pool, missing outcomes remain represented, and sparse cohorts fall back explicitly.
