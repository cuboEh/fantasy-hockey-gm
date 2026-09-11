# Draft model validation and final-roster coverage

September 11, 2026. This increment followed the agreed sequence: historical replay,
forecast-versus-decision errors, completed-roster goalie coverage, and review of
assumption-sensitive choices. No projection weights were tuned. The dashboard's
ordinary board and comparison remain unchanged.

## What the historical replay establishes

The existing research runner now has a bounded `--working-replay` mode. It uses
2021-22 through 2023-24 observations to forecast 2024-25, fixes the draft cutoff at
September 26, 2024, and writes all nine drafts before opening 2024-25 outcomes.
Three policies run at seats 1, 7 and 14 against the same synthetic opponents:
league-points first, historical market proxy, and two-pick roster opportunity.
The planner's two preference seeds differ from the realized opponent seed.

This tests the opportunity decision method with a fixed historical rate/GP model.
It does **not** test the accuracy of today's DtZ projections. The historical
comparison also lacks archived Yahoo eligibility and authenticated historical
Yahoo rankings. Its ADP is a CSG workbook column attributed to Yahoo/FantasyPros,
retrieved from a mutable file in 2026. Publication in 2024 does not prove that the
file was unchanged. Missing ADP falls behind supplied ADP, then follows projected
points. Rookies without prior NHL observations are omitted.

Two defects were found and addressed:

1. The older `scenario_two_turn` study supplied the planner with the exact realized
   opponent order. Future runs use a distinct planning seed. Existing studies are
   preserved and must not be cited as validation of the corrected method.
2. A three-season history retained departed players such as Bergeron and Koskinen.
   The new replay now requires an appearance in the immediately preceding season.
   This uses no target outcomes, but conservatively excludes full-season absentees
   and returnees as well. It is an eligibility proxy, not an authentic draft pool.

The initial defective-pool run is retained in `var/working-historical-2026-09-11/`.
The corrected diagnostic is `var/working-historical-2026-09-11-v2/`.

### Corrected provisional results

| Draft seat | Points first | Market proxy | Two-pick opportunity |
| --- | ---: | ---: | ---: |
| 1 | 7,185.3 | 6,845.1 | 7,737.2 |
| 7 | 6,997.6 | 6,189.3 | 7,399.4 |
| 14 | 6,754.6 | 6,130.3 | 8,088.3 |

These are **provisional season points**, not verified performance gains. They
assume absent outcome rows produce zero points. The strict audit instead flags
missing selected-player observations and recorded provider disagreements, then
compares only weeks complete for every policy. There are zero common complete
weeks at seat 1 and just one at seats 7 and 14. Those small remaining weeks do not
support meaningful comparisons. Source completeness is a blocker to validation,
not a reason to treat missing rows as confirmed scratches.

Other limits: single historical position; last observed team rather than offseason
roster knowledge; prior calendar for draft valuation; final reconstructed calendar
for daily decisions; fixed preseason forecasts; no injury news or confirmed goalie
starters; no transactions. Monday-Sunday goalie qualification, including short
calendar weeks, is not verified Yahoo matchup scheduling. Previously studied
seasons are diagnostic data, not untouched holdouts.

## Forecast errors versus decision errors

Each roster has player-level signed FP errors, using:

```
workload error = (observed GP - projected GP) * projected FP/GP
rate error = observed FP - observed GP * projected FP/GP
```

Their sum equals the season-point forecast error, including zero observed games.
No observations remain explicitly flagged, not certified as zero NHL appearances.
The report separately records bench production and goalie points lost to the
minimum-appearance rule, so those losses are not confused with projection errors.
These accounting components diagnose the run; they do not identify causes of
injury, role change or scoring-rate decline by themselves.

At seat 1, the corrected points-first roster had approximately -788 FP of workload
error and -803 FP of rate error. The two-pick roster had approximately -1,230 and
-1,025 respectively: its apparent gain did not come from more accurate forecasts.
Provisional bench points were 1,645 versus 412, suggesting lineup congestion is a
useful mechanism to investigate. Bench production is not all recoverable value;
it can also reflect unexpected performance, stale team metadata and the fixed
lineup policy. Evander Kane's zero observed appearances remain a major two-pick
workload miss, illustrating the need for dated health/availability evidence.

## Completed-roster goalie comparison

A reusable `completion_options` function now evaluates legal choices for the final
roster place. It only runs with exactly one place left. It compares skater usable
production with qualified goalie production using separately reviewed start counts
and shrunk per-start rates. Qualification **replaces** the goalie contribution in
this calculation; it is not added to appearance-based points as a bonus.

No GP-to-start conversion is invented. Missing goalie scenarios exclude affected
comparisons. Same-team starting budgets remain constrained. Baseline and downside
results remain separate conditional cases. Relief appearances, known-starter
lineup changes, streaming and verified Yahoo week boundaries are not modeled.

The existing current-board rehearsal was audited at three final-pick states:

- **Seat 1:** Will Cuylle remained the preferred final pick in both cases. Dustin
  Wolf would reduce the baseline failed-calendar-week proxy from 5.57 to 2.32,
  but sacrifice 386.1 usable skater FP while adding 347.3 qualified goalie FP.
  Net baseline difference: **-38.8 FP**. Better coverage is not free.
- **Seat 7:** Wolf narrowly led the original Joey Daccord pick by **2.25 FP** in
  the baseline starter scenario. The downside case preferred Dylan Cozens instead.
  That small, assumption-sensitive difference is not strong evidence to switch.
- **Seat 14:** Cuylle remained preferred; that roster already held three goalies.

These are current-model conditional projections, not realized outcomes. There is
no blanket two-goalie or three-goalie rule. The final-pick evaluation is exposed
through the existing CLI for review, not installed as a new automatic dashboard
ranking:

```sh
uv run fantasy draft-plan --working-board --method completion \
  --db YOUR_ON_CLOCK_FINAL_PICK_SESSION.sqlite \
  --schedule var/schedule-20262027-2026-09-10.json \
  --workloads private/goalie-workload-review-2026-09-10-v2.json \
  --rates var/goalie-start-rates-2026-09-10.json \
  --as-of 2026-09-11 --json
```

Refresh reviewed inputs when material facts change. This command rejects an
unfinished early-round roster rather than penalizing it for missing partners.

## Which assumptions deserve attention

The audit inspected all 48 own turns from the three current-board two-pick drafts.
It saved differences between baseline, downside and minimum-regret choices and
attached existing review evidence. This is a review queue, not fresh news research
or a probability of player failure.

A concrete case is seat 1, pick 112, immediately before another pick at 113:

| Pair | Baseline added lineup FP | Existing conditional stress FP |
| --- | ---: | ---: |
| John Gibson + Jet Greaves | 1,085.22 | 813.91 |
| J.T. Miller + Jet Greaves | 1,083.98 | 947.60 |

The two-goalie pair's baseline lead is only **1.24 FP**. No opponents pick between
these turns, so availability uncertainty cannot explain the difference here.
The result depends on projected value and the asymmetric stress inputs: both
goalies are stressed, while Miller has no transferred downside case. This does
not establish that Miller is safe or that the risk-adjusted ranking is calibrated.

Prioritize reviewing Gibson/Greaves/Daccord/Wolf start shares and the GP/role
assumptions for Miller, Cozens and Hamilton. The broader queue also surfaces
Svechnikov and Cuylle. A player's frequency in sensitive decisions can reflect its
partner or an alternative's assumptions, not that player's own uncertainty.
Do not fit weights to make these few examples produce a preferred answer.

## Reproduction and checks

Both research modes reuse existing scripts. No new provider, service or dashboard
infrastructure was introduced. Private data and generated reports stay ignored.

```sh
uv run python research/validate_draft_planning.py --working-replay \
  --seats 1 7 14 --output-dir var/working-historical-repeat

uv run python research/rehearse_planner.py \
  --audit-working var/working-policy-diagnostic-2026-09-11 \
  --board var/mvp1-2026-09-11-final/board.json \
  --schedule var/schedule-20262027-2026-09-10.json \
  --workloads private/goalie-workload-review-2026-09-10-v2.json \
  --rates var/goalie-start-rates-2026-09-10.json \
  --as-of 2026-09-11 --output-dir var/working-completion-repeat
```

The completion/sensitivity artifacts are in
`var/working-completion-audit-2026-09-11/`. The additional pick-112 case study and
public integration-function check are saved there too. Source/input hashes and
frozen picks accompany the diagnostics. Output directories must be new.

All **147 tests passed**, including pre-draft input rejection, stale-player
eligibility, exact error accounting, missing-outcome handling, final-roster
qualification and the opportunity cost of an additional goalie. The public
completion integration was exercised against a saved final-pick rehearsal.
The live session still has seven picks, revision 7, and no assigned slot. No live
picks or forecasts were changed, and no dashboard restart was necessary.

## Next steps

1. Before September 13, refresh the small set of material workload/role assumptions
   above and show close alternatives as uncertain choices. Preserve the dependable
   board and obtain the actual draft slot when available.
2. Before using historical results to tune weights, audit game-level participation
   coverage and dated preseason eligibility. Distinguish verified nonappearance
   from missing provider data. Obtain authenticated historical market/projection
   snapshots where possible. Do not substitute current information into old drafts.
3. Repeat the frozen comparison only after those inputs improve. Keep the current
   method experimental until its advantage survives meaningful, complete outcomes.
