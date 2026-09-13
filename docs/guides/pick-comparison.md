# Pick now versus wait

Implemented September 11, 2026 as an experimental MVP 1 decision tool. It reuses
`draft_planner`, `draft_value` and the frozen working board. No new dependency,
external data download, forecast fitting or separate optimizer was introduced.

## Use it

Refresh the dashboard. Set your actual draft slot, then use **Compare my next two
picks** when your team is on the clock. The comparison does not record a pick.
It displays an added-lineup-value estimate, later options, opponent sensitivity,
and a separate conditional stress result. The ordinary season-points board remains
available for inspection. Pick entry and undo remain unchanged.

The desktop launcher now supplies the validated upcoming schedule. A direct launch:

```sh
uv run fantasy dashboard --db var/draft-mvp1-2026-09-11.sqlite \
  --schedule var/schedule-20262027-2026-09-10.json --open
```

Results are cached for the exact revision and schedule contents. A slot change,
pick, undo or eligibility edit invalidates old advice. Calculations use a consistent
snapshot and do not mutate the tracker. An owned player without a supported
forecast blocks the comparison with an explanation; manual tracking still works.
Unknown slots and other teams' turns also leave the comparison unavailable.

## What changed in the decision model

1. Use the working provider forecast and supplied Yahoo eligibility, not the older
   historical/goalie-only experimental valuation. Correct Yahoo/NHL team aliases
   at the schedule boundary. Unsupported players cannot be recommended, although
   they remain in opponent simulations and observed pick histories.
2. Spread projected appearances over the player's team schedule. Match the resulting
   daily point opportunity to actual active slots, including multi-position
   eligibility. Compare the roster with and without a candidate. Production that
   displaces an existing player or lands on a full night has less incremental value.
3. Simulate picks until the next snake turn under four shared opponent orders:
   two ADP orders with 10% jitter, a displayed-Yahoo-rank order, and a sensitivity
   case that substitutes displayed rank when drafted percentage is below 50%.
   The threshold and jitter are explicit hypotheses, not learned parameters.
4. Compare the first player plus the best later option within a bounded shortlist.
   Include the straight-points choice, first supported Yahoo-rank choice and best
   current incremental option even if they fall outside the normal shortlist.
5. Stress the same player pair using documented earlier downside/base FP ratios.
   Apply the ratio to the working FP rate, leaving working GP unchanged. This is
   an aggregate conditional stress, not a predicted injury or a fitted forecast.
   Fifty-five players have a usable transferred stress; all others are unmodified,
   which does not make them risk-free.

The initial and later search shortlists contain high raw-value players and
position-specific alternatives. The first shortlist also includes the best
current incremental option. This does not exhaust every possible pair or optimize
the remaining draft. Missing ADP is not zero, and opponent survival fractions are
not probabilities. The mean is across chosen hypotheses, not their estimated
real-world likelihoods. Tied choices should not be read as meaningful separation.

## Two important corrections

**Unfinished goalie rosters:** the original planner applied weekly qualification
to partial rosters. The new draft comparison values daily goalie-slot opportunity
without forfeiting an unfinished team's goalie points. Provider appearances are
not verified starts, so they are not passed into the exclusive-starter coverage
model. Weekly minimum coverage remains a separate requirement before finishing
the roster. This neither forces early goalies nor assumes that two goalies suffice.

**Fixed pair under stress:** the original planner could choose a different later
player in each downside case. The working comparison retains the baseline-selected
later player when stress-testing that branch. This avoids crediting a pair with
an adaptation the user has not actually made. Legacy research mode retains its
separate-case behavior; the working mode is explicit.

Maximum regret is the largest shortfall from the best compared first pick in any
opponent/stress case. It is a sensitivity summary, not a risk probability. The
smallest-regret alternative is shown alongside the highest mean-value plan.

## Verification and bounded diagnostic

141 tests pass. New cases cover a scarce winger beating the higher-scoring center
when center depth survives the next turn; off-night value beating a congested
higher-rate player; goalies retaining opportunity value in partial rosters;
fixed later picks under stress; future inputs, bad opponent orders and missing
owned forecasts; NHL/Yahoo team aliases; read-only comparison caching and stale
revision rejection. Browser checks confirmed comparison rendering, recording a
pick from its cards, clearing stale advice, and undo in a separate practice session.

Nine complete synthetic drafts compared three policies at seats 1, 7 and 14. Every
policy faced the same additional ADP-based opponent preference order (seed 33),
which was not among the four planning orders. No realized NHL outcomes were used.

| Seat | Points-first lineup proxy FP | Yahoo-rank-first proxy FP | Two-pick proxy FP | Change vs points-first |
| --- | ---: | ---: | ---: | ---: |
| 1 | 9,493.9 | 8,075.9 | 9,512.3 | +18.4, about 0.2% |
| 7 | 9,342.1 | 7,622.5 | 9,418.7 | +76.6, about 0.8% |
| 14 | 9,305.3 | 7,771.9 | 9,413.9 | +108.6, about 1.2% |

The maximum comparison time in this diagnostic was 2.35 seconds. Most earlier
single-state checks were below one second. The two-pick policy selected three
goalies in seats 7 and 14, and two in seat 1. A separate calculation using the
existing analyst starter scenarios estimated 2.13 failed calendar weeks for those
three-goalie rosters versus 5.57 for the two-goalie points-first rosters. These are
coverage proxies with unverified Yahoo week boundaries, not predicted actual
failures or a guarantee that a third goalie is necessary. Coverage remains a concern.

These are modest current-model gains, not evidence of better real-season results.
Choosing and scoring with the same forecasts favors the model's own assumptions.
Only three seats and one additional opponent order were checked. The larger gap
against Yahoo ranking is particularly unsuitable as a claim about beating real
managers. No weights or thresholds were tuned to improve these diagnostic results.

Local artifacts:

- `var/working-policy-diagnostic-2026-09-11/report.json`: nine terminal rosters,
  comparisons, input/source hashes and per-turn timing.
- `var/working-policy-diagnostic-2026-09-11/goalie-coverage.json`: separate coverage check.
- `var/working-comparison-tests.log`: test run.
- `var/working-dashboard-practice.sqlite`: isolated browser rehearsal.

Reproduce into a new directory:

```sh
uv run python research/rehearse_planner.py --working-board \
  --board var/mvp1-2026-09-11-final/board.json \
  --schedule var/schedule-20262027-2026-09-10.json \
  --as-of 2026-09-11 --output-dir var/working-policy-repeat
```

For a saved on-clock session, use `fantasy draft-plan --working-board --db ...
--schedule ... --as-of 2026-09-11 --json`. Its optional `--output` writes a new
immutable decision snapshot. The live slot and seven already-recorded picks were
preserved during installation; test seats were never applied to the live session.

## Remaining limits and next validation

Daily matching uses season-average availability. It does not simulate injury timing,
backup substitutions when an absence becomes known, confirmed goalie starts,
streaming, playoff weighting or how a role changes during the season. Later bench
construction and long-range position scarcity can defeat a two-pick horizon.

The existing historical diagnostic covers previously explored seasons such as
2018, 2022 and 2026. It uses different projection/coverage policies and is not an
untouched validation of this working model. Do not relabel those results or feed
2026 Yahoo rankings, DtZ forecasts or current role notes into old drafts.

Next meaningful validation is a dated historical replay specification with forecasts
and eligibility available before each draft, appropriately dated market data where
available, explicit schedule knowledge assumptions, and separate outcome scoring.
Run the same policies and lineup rules against it. Then assess forecast error,
counted weekly points and goalie-minimum failures, rather than tuning to these nine
current-forecast mock drafts. Keep the comparison experimental until that evidence
supports stronger claims. Material September 13 health/role news still needs review.

## September 11 follow-up

The [validation and final-roster report](../archive/validation-2026-09-11.md) supersedes the
validation next step above. The historical diagnostic exposed stale eligibility,
opponent foresight in an older study, and incomplete participation observations.
Those findings prevent promotion to a proven model. A separate final-pick coverage
comparison now prices the skater sacrificed for another goalie; it does not change
early-round rankings or automatically replace the dashboard comparison.

## September 12: statistical pick explanation (PRD P2)

The summary now names the suggested pick and points-first alternative. It shows
both projected season totals, their signed difference, and the projected added
lineup difference over the same horizon. The explanation separates value from the
current pick and value from the later selection. These are conditional projected
benefits, not demonstrated season gains or a fitted breakout score.

Every compared candidate is inspectable. Expand its later-options section to see
both player pairs under each shared opponent case, their projected added lineup
points and signed difference. Yahoo rank and ADP are separate price context;
missing values say unavailable. A plan tied with points-first retains points-first.
On the final turn, the button, summary and cards show one-pick value without a
later selection. Existing goalie-qualification limitations still apply.

The working-board CLI prints the same tradeoffs and paired alternatives. Use
`--limit` to control candidate verbosity; JSON retains the complete comparison.
See [PRD acceptance evidence](../PRD-1.0.md) for checks and remaining phases.

## September 12: uncertainty and release rehearsal (PRD P3/P4)

Expand the assumption-sensitivity summary to see which tested opponent or
conditional stress case favors a different first pick and by how many projected
lineup points. A stable choice means only that no tested case preferred another
player. It does not establish low risk. Missing individual stress cases remain
unassessed, and scenario counts are not availability probabilities.

Player details expose conditional case dates/sources and the earlier role or
workload assumptions. Earlier goalie starts are distinguished from the working
projection's appearances. The underlying forecast is unchanged by these labels.

The guide passed the isolated pick/undo, stale-state, reload, backup and CSV
rehearsal. The [PRD](../PRD-1.0.md) records the complete acceptance evidence.
