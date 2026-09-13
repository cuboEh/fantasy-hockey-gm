# Completed-roster planning experiment

September 10, 2026. This increment targets an observed failure of the two-turn
planner: postponing the first goalie because an incomplete goalie group has low
counted value. It adds a full-draft rollout, a stronger availability test, and
paired uncertainty reporting. It does not establish a future league advantage.

## Results and decision

The fixed main study completed **36 full 14-team drafts across 12 seasons**, three
policies per season at seat 7. A separate three-draft pilot preceded it and is not
counted again in the aggregate. The live strategy remains unchanged.

| Policy | Counted FP | Missed weeks | Weekly all-play score |
| --- | ---: | ---: | ---: |
| Existing coverage | 6,749.9 | 6.33 | 56.82% |
| Revised starter coverage | 6,677.8 | 4.75 | 55.97% |
| Completed-roster planner | 6,748.5 | 4.50 | 57.15% |

Full-draft planning averaged **-1.4 FP and 1.83 fewer missed weeks** relative to
coverage. It gained points in 5/12 seasons. The descriptive season-bootstrap
interval for its mean point difference was approximately **-432 to +392 FP**.
The all-play difference was only **+0.32 percentage points**. These results do not
establish a reliable advantage and do not justify replacing the default.

The aggregate hides instability. In 2015-2020, completion was -34.7 FP with 6.33
fewer missed weeks; in 2021-2026 it was +32.0 FP with 2.67 more missed weeks.
Different realized preference seeds were used for these blocks. Better average
rate accuracy did not automatically produce better draft decisions: the revised
starter-coverage variant lost 72.1 counted FP overall.

All 118 tests pass. Baseline single-seed and downside three-seed CLI smoke checks
passed using an isolated persisted mid-draft state. Full historical completion
planning took about 72-76 seconds per entire 16-pick own draft in the concurrent
runs. This is not a per-pick latency guarantee, and full-draft search remains
optional experimental advice.

Artifacts remain local and ignored:

- `var/completion-early-2026-09-10/`
- `var/completion-later-2026-09-10/`
- `var/completion-paired-2026-09-10.json`
- `var/completion-early-all-play-2026-09-10.json`
- `var/completion-later-all-play-2026-09-10.json`
- `var/completion-current-smoke-2026-09-10.json`
- `var/completion-current-downside-2026-09-10.json`

Next development should address forecast uncertainty and the opportunity cost of
premium goalie picks, using dated workload/team context and independent preseason
projections where available. Any risk rule needs a separate fixed comparison;
the observed losing goalies must not simply become retrospective exclusions.
More seeds and draft seats remain necessary before a promotion claim, but the
current result does not warrant treating this version as a winner.

## Method

For each shortlisted pick, simulate every remaining snake pick. Opponents follow
fixed noisy ranking preferences and obey roster constraints. Our later choices
follow a fixed usable-production plus goalie-insurance policy, using the reviewed
starter exposures. Score the resulting complete roster with daily lineup capacity
and weekly goalie qualification. Compare terminal fantasy points and missed-week
estimates, preserving a lower-risk alternative and its points cost.

This accounts for future goalie partners when valuing the first goalie. It also
charges the opportunity cost of roster spots those partners occupy. No actual
future performances, injuries, transactions or draft outcomes enter selection.

The continuation is a heuristic, not a solved optimal draft. It uses primary
positions for its marginal-value approximation; terminal evaluation and roster
legality support multiple positions. Candidate shortlists contain top raw values
and positional alternatives, so excluded players may be better. Full-draft
rollouts cost more than two-turn advice. Unsupported owned projections or an
uncompletable supported roster produce an explicit error.

## Fixing an evaluation weakness

Earlier two-turn diagnostics supplied the exact synthetic opponent preference
order used by the simulated draft. Those tests measured a favorable availability
assumption. They did not leak NHL outcomes, but they gave more precise draft
knowledge than we should expect in practice.

The completion experiment uses planning preference seed 10001 and different
realized preference seeds, 0 or 1. Preferences stay fixed across candidate branches
within a planning scenario, but the planner cannot see the realized future order.
Rank-following style remains an assumption. Actual historical Yahoo ADP is still
missing, so both orders use synthetic market rankings.

Three policies separate effects:

1. `coverage_frozen`: existing usable-production and goalie-insurance strategy.
2. `starter_coverage`: insurance selection using the revised starter exposures and
   a positional shortlist. This is an ablation of the revised inputs and shortlist,
   not an isolated causal test of shrinkage alone.
3. `scenario_completion`: full-draft rollouts with the same revised projections.

Replay lineups use the same frozen baseline forecasts for every policy. Results
compare common conflict-free weeks. No streaming, actual H2H opposition, or
current contextual news is injected into history. Zeroing goalie production when
minimums are missed remains the explicit penalty scenario being evaluated.

## Local usage

Use the existing `fantasy draft-plan` inputs from the
[two-turn guide](two-turn-draft-planning.md), adding:

```text
--method completion --case baseline --seeds 10001 10002 10003
```

Use `--case downside` for a separate conditional case. Scenario differences are
not probabilities. Output shows completed-roster points, expected missed weeks,
and a coverage alternative's points cost. JSON retains full simulated pick traces,
terminal rosters, goalie groups and ranges across preference seeds. A one-seed
range has no uncertainty information. These values are model estimates, not
promised fantasy totals.

The command is read-only. The current live draft session remains untouched, and
its actual slot still needs to be supplied. A persisted mid-draft smoke check ran
in the isolated practice session.

## Reproduce the fixed comparison

```bash
uv run python -m research.validate_draft_planning \
  --years 2015 2016 2017 2018 2019 2020 --seats 7 --styles rank \
  --policies coverage_frozen starter_coverage scenario_completion \
  --output-dir NEW_EARLY_DIRECTORY

uv run python -m research.validate_draft_planning \
  --years 2021 2022 2023 2024 2025 2026 --seats 7 --styles rank --seed 1 \
  --policies coverage_frozen starter_coverage scenario_completion \
  --output-dir NEW_LATER_DIRECTORY

uv run python -m research.summarize_draft_comparison \
  --directories NEW_EARLY_DIRECTORY NEW_LATER_DIRECTORY \
  --output NEW_PAIRED_REPORT.json
```

Seasons are identified by ending year. All were explored previously. The two
blocks were specified before their results were observed; neither is an untouched
holdout. Early and later blocks use different realized seeds, so seed and era are
confounded. Results apply to seat 7, not all draft seats. The summarizer resamples
season means with a fixed seed to describe variability. Its interval does not
measure the probability of beating friends or winning a league.

## Next evidence required

Before promoting the new strategy, check positive points and no worsening of
missed minimums across both era blocks, then expand to edge seats, additional
opponent styles and more independent preferences. Avoid repeatedly choosing new
weights based on the same historical seasons. Keep the September 10 prospective
forecast snapshot unchanged and version any subsequent decision policies.

A practical advantage also depends on draft-room rankings and eligibility, rookie
coverage, current deployment and health evidence, and active in-season management.
Those remain separate inputs and tasks. More exhaustive search cannot recover
missing or systematically wrong projections.


## Weekly all-play diagnostic

`research.evaluate_all_play` replays every simulated team's locked roster with the
same baseline lineup forecasts, then compares our score with all 13 opponents in
each week. Ties count half. Comparisons retain common conflict-free opponent/week
pairs across policies, rather than comparing different clean-week samples. Input
hashes must still match the original experiment manifest before replay begins.

This describes the distribution of weekly performance. It is not a real matchup
record or championship probability. Opponents' rosters can change as our draft
choices change, and no streaming is included. Reproduce after the draft studies
have completed:

```bash
uv run python -m research.evaluate_all_play \
  --directories NEW_EARLY_DIRECTORY NEW_LATER_DIRECTORY \
  --output NEW_ALL_PLAY_REPORT.json
```

## Diagnosing losses without retuning on them

The 2017 completion roster used picks 7 and 22 on Bishop and Schneider. Their
projected starter rates were 12.27 and 11.52 FP; realized clean starter rates were
10.16 and 9.85. Bishop supplied 37 clean starts against about 60 projected on the
prior calendar. This roster had substantially better qualification but lower
counted total points than the reference. Coverage alone does not justify the
skater opportunity cost of premium goalie picks.

In 2022, the completion roster selected Blackwood, Jones and Bernier later. The
historical model retained prior-team identities and Bernier supplied only eight
clean starts. This illustrates workload and team-context risk. The previous
calendar was shortened, so raw projected and actual start counts must not be
compared as equal-length season forecasts.

These are post-hoc explanations, not new exclusions or tuned penalties. The
locked experiments were allowed to finish without changing their selection rule.
Private diagnosis: `var/completion-loss-diagnosis-2026-09-10.json`.
