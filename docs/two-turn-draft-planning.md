# Draft planning improvements, September 10, 2026

The helper now connects reviewed workloads and selected context cases to usable
roster points, compares picking now with waiting until the next snake turn, and
reports a goalie-coverage alternative when one is available. This is optional
experimental advice. Keep the existing coverage strategy as the working reference:
the new two-turn strategy did not improve its points against rank-following
opponents and missed more goalie minimums.

## What changed

- `goalie_rates.py` separates starts and relief using historical starter flags.
  Starter rates shrink toward other goalies' starter cohort with 20 fixed prior
  observations. Flagged source conflicts are excluded; missing samples remain
  unsupported. Start allocations receive starter rates, without adding relief
  production or counting relief appearances as starts.
- `draft_value.py` values expected production in usable daily roster positions.
  It handles overlapping positions, bench congestion, and joint weekly goalie
  minimums. Baseline and downside remain separate conditional scenarios.
- `draft_planner.py` compares shortlisted picks across the next two own turns.
  Opponents use fixed noisy preferences, obey roster constraints, and remove
  intervening picks. Each branch records its later choice and complete pick trace.
- `decision_cli.py` joins reviewed workloads, starter estimates, and explicitly
  selected skater context cases by player ID. It checks dates, seasons and input
  hashes and reads the draft database without changing picks or rankings.
- A coverage alternative exposes the estimated points cost of reducing missed
  goalie minimums among the compared plans. It requires an existing goalie and
  plans ending with at least two. It is not a globally optimal insurance policy.
- Draft export reconstruction now preserves your roster's recorded pick order.
  Forecast snapshots and evaluation manifests retain input and code fingerprints.

Current context mappings cover Brady Tkachuk, Aleksander Barkov, and Seth Jarvis.
Other skaters retain their existing projections. Reviewed goalie workloads are
analyst scenarios, not reported start forecasts. Neither case has an assigned
probability. Changes in recovery timing are currently averaged over the season
when used by this planner, so dated IR replacement is not modeled here.

## Local commands

From the repository, build starter estimates from cached permitted data:

```bash
uv run python -m tools.build_goalie_rates \
  --history var/history-2026.json \
  --goalie-box snapshots/2026-09-10/sportsdataverse/goalie_box_2026.csv \
  --config config.local.toml --as-of 2026-09-10 \
  --output var/goalie-start-rates-2026-09-10.json
```

The output already exists locally. Writers require a new output path to preserve
previous runs. Once your actual slot is set and your team is on the clock:

```bash
uv run fantasy draft-plan \
  --db var/draft-14-reviewed.sqlite \
  --schedule var/schedule-20262027-2026-09-10.json \
  --workloads private/goalie-workload-review-2026-09-10-v2.json \
  --rates var/goalie-start-rates-2026-09-10.json \
  --context var/context-pilot-2026-09-10-v3.json \
  --case-map private/draft-context-case-map-2026-09-10.json \
  --as-of 2026-09-10
```

Use `--output NEW_PATH.json` to retain an auditable recommendation, `--json` for
full branch details, and `--opponents points` or `--opponents goalie_early` for
sensitivity checks. Default advice uses three synthetic opponent seeds. The
existing `fantasy draft-guide` remains available. Your live session's slot is
still unset, and no rehearsal set it or recorded live picks.

## Validation results

### Starter rates

Across seasons ending 2015 through 2026, 623 paired returning-goalie cases with
at least 20 clean target-season starts had these mean absolute errors in fantasy
points per start:

| Previous-data estimate | MAE |
| --- | ---: |
| Existing blended per-appearance baseline | 1.83 |
| Raw prior-season starter rate | 2.03 |
| Shrunken prior-season starter rate | 1.51 |

Shrinkage reduced error by about 17% against the existing baseline and improved
all 12 annual means. This conditional returning-starter comparison does not
validate workload predictions, injured absentees, rookies, or draft outcomes.
Artifact: `var/starter-rate-validation-2026-09-10.json`.

### Draft and season replay

The frozen comparison ran **216 complete 14-team drafts**, four policies across
54 scenarios. Core: 12 season-end years, 2015 through 2026, rank-following
opponents, seats 1/7/14. Stress: 2018/2022/2026, points-following and goalie-early
opponents, the same seats. Each scenario uses one fixed preference seed shared
across policies. Results below use each scenario's common conflict-free weeks.

| Policy | Core counted FP | Core missed weeks | Stress counted FP | Stress missed weeks |
| --- | ---: | ---: | ---: | ---: |
| Frozen points | 6,481.9 | 8.17 | 7,480.8 | 12.89 |
| Existing coverage | 6,800.3 | 6.17 | 7,864.1 | 9.78 |
| Scenario greedy | 6,801.2 | 13.75 | 7,667.7 | 19.33 |
| Scenario two-turn | 6,800.2 | 8.25 | 7,938.7 | 11.50 |

Two-turn planning essentially tied coverage points in the core comparison while
missing 2.08 more minimums. Stress gained 74.7 points but missed 1.72 more minimums.
Greedy selection's severe goalie weakness argues against promoting a model just
because its aggregate points look competitive. The coverage alternative was
added as reporting after these runs and was not evaluated as a selection policy.

These are diagnostic replays, not untouched holdouts or H2H win-rate estimates.
Those historical seasons have been explored previously. The two-turn policy also
received the exact synthetic opponent order used by its simulated draft, making
availability more predictable than in practice. The follow-up
[completed-roster experiment](completed-roster-planning.md) separates planning
preferences from realized preferences. Selection receives only
prior histories and prior schedules. Target outcomes are scored after drafting;
all policies use the same frozen baseline daily-lineup estimates. There are no
streams, current-news labels inserted retrospectively, or actual historical Yahoo
ADP. Prior team codes missing from the calendar are explicitly unsupported rather
than guessed. Source-conflicted weeks are excluded consistently across policies.

Artifacts:

- `var/planning-rank-validation-2026-09-10-v2/`
- `var/planning-opponent-stress-2026-09-10-v2/`

Each contains its locked manifest, picks, replay weeks, rows and summary. Reproduce
with `tools.validate_draft_planning --help`; use new directories. Earlier failed
runs are retained, including the historical team-code issue that was corrected.

### Workflow and prospective evaluation

`var/planner-rehearsal-2026-09-10-v2/report.json` records all 14 seats, 3,136 legal
picks and 224 own-turn recommendations. Rehearsals checked persistent mid-draft
advice, no database mutation from advice, backup recovery, undo/re-entry and full
export reconstruction. Maximum single-seed advice time was about 0.69 seconds
on this machine, not a guarantee for other machines or larger searches. A separate
three-seed mid-draft CLI smoke check also passed.

`var/prospective-2026-09-10/forecasts.json` freezes all 470 current player entries,
including unsupported estimates, with separate workload, rate and season-point
evaluation rules. Retain this original when making later revisions. Future
outcomes can test this snapshot without retrospectively altering its assumptions.

All **116 tests pass**, including starter/relief separation, missing/conflicting
inputs, usable-position matching, legal waiting simulations, coverage reporting,
seed validation and deterministic export reconstruction.

## Remaining priorities before the draft

1. Obtain your actual draft slot, current Yahoo eligibility and draft-room ranking
   export or manually supplied rankings. The current partial market proxy is not
   Yahoo ADP. Refresh high-impact health and role evidence near draft time.
2. Fill supported rookie/missing projections, particularly any plausible draft
   target currently excluded from scenario advice.
3. Keep coverage guidance visible. Test a longer-horizon goalie-completion policy
   separately before replacing the working strategy. Two-turn search can postpone
   the first goalie because an incomplete goalie group has little counted value.
4. Add dated absence/IR replacement and Yahoo's actual matchup calendar when
   available. Calendar-week assumptions are provisional; waiver rules are unknown.
5. Evaluate the frozen current forecasts prospectively. Expand historical tests
   with genuinely dated context and market data before claiming contextual gains.

No Yahoo API access, scraping, browser automation, or roster writes were used.
Private configuration, source downloads and generated results remain ignored.
