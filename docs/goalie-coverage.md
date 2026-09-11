# Weekly goalie coverage, September 10, 2026

The draft simulation now values protection against missing the league's three
active goalie appearances per week. Previously, usable-game valuation only
credited each goalie's own production. It ignored the points a supporting goalie
can protect for the rest of the goalie roster.

## Implementation

`goalie_coverage.py` adds the reduction in expected forfeited goalie points to
ordinary marginal usable production. An unfinished roster is not penalized for
having no partner yet. This is an insurance-credit heuristic, not an exact global
roster optimum. It can select a third goalie, but does not require one.

A probability/reward dynamic program calculates points conditional on reaching
three appearances. It tracks points jointly with appearance counts. Same-team
goalies share a single start opportunity, with probabilities normalized across
the forecast pool when their combined workloads exceed one starter per game.
Daily selection respects the two goalie slots. Expected appearance frequency is
a proxy for start frequency; relief appearances are not modeled.

Historical decisions use only prior forecasts, team identities and the prior
season calendar. No target-season injuries or outcomes enter the utility.
All utility policies retain the same top-12 fitting candidate shortlist and
opponent preference seeds. Candidate search is still limited, and forecasts for
former teammates can dilute same-team probabilities. Independent game events
do not capture prolonged injuries or deployment changes.

## Paired replay results

Nine seasons ending 2018 through 2026, two seeds and seats 1, 7 and 14: 54 drafts
per policy, 378 total across seven policies. No streaming. Weekly goalie points
are removed when fewer than three active appearances occur.

| Forecast family | Missed weeks before | After | Counted FP change | Goalies drafted before | After |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline usable | 5.80 | 4.41 | +22.0 | 2.39 | 2.81 |
| Analogue usable | 8.87 | 7.15 | +18.6 | 2.19 | 2.52 |

Baseline coverage improved mean counted points in six of nine seasons. Excluding
the two pandemic seasons, its mean improvement was +25.7 points. Its 2024 result
was worse by 248.0 points, so insurance can be overpriced relative to skater
opportunity. The incremental H2H result was +0.17 wins per season for baseline
coverage and +0.02 for analogue coverage, using common conflict-free weeks.
Full-season FP include flagged historical source conflicts. These already
explored seasons are diagnostic evidence, not an untouched validation set.

The problematic 2025 seed-0 seat-14 analogue draft improved from 22 missed weeks
to 13, with +124.2 counted points. That is still inadequate coverage. The more
stable baseline forecast remains preferable for goalie risk guidance; the
analogue forecasts are not promoted to the live board. A better objective cannot
repair an inaccurate injury or workload forecast by itself.

Private full results: `var/goalie-coverage-2026-09-10/`. Reproduce into a new folder:

```bash
uv run python -m tools.replay_analogue_drafts \
  --history-dir var --config config.local.toml \
  --output-dir var/goalie-coverage-repeat
```

## Draft-day use

The existing guide now warns that filling two goalie slots does not guarantee
three active appearances. Optional read-only coverage advice uses an explicitly
supplied completed calendar:

```bash
uv run fantasy draft-guide --db var/draft-14-reviewed.sqlite \
  --goalie-calendar var/history-2026.json
```

Once your slot and picks are recorded, this reports goalie insurance credits
for the owned roster, separately from the unchanged baseline player ranking.
The credits are neither added season projections nor calibrated probabilities.
They use current board workloads normalized for its 84-game season and the old
calendar as a proxy. The calendar hash is included in JSON output. Missing owned
goalie inputs disable the estimate; missing candidate inputs are listed as
excluded. Candidate roster fit still needs checking. No slot or owned goalies
means there is no existing goalie investment to evaluate.

## Remaining development

1. Review goalie workloads and dated health/role evidence before the draft,
   especially shared jobs. Use downside scenarios rather than predicting injuries.
2. Replace the prior-calendar proxy with the actual upcoming schedule when a
   permitted source is available, and show week-specific coverage bottlenecks.
3. Test a wider candidate search and multi-pick planning without forcing a goalie
   quota. Keep benchmarks frozen and reserve new seasons for prospective evaluation.
4. During the season, recalculate coverage as appearances occur and add streaming
   once waiver timing is known. A draft-only roster cannot ensure every minimum.
