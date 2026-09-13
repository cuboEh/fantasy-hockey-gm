# Analogue forecasts tested in 14-team drafts

The first replay does **not justify promoting analogue corrections over the
usable-game draft strategy**. Better average player prediction did not reliably
translate into better roster decisions.

Nine target seasons, 2017-18 through 2025-26, were replayed with two opponent
preference seeds, seats 1/7/14 and five policies: 270 complete 224-pick drafts.
Opponents retain the same ranking preferences across policies. Their resulting
rosters change naturally when our picks change; player ownership is exclusive
within each draft. Opponent daily lineups always use the baseline forecast.

## Paired results

Mean differences relative to points-based baseline drafting:

| Policy | Draft-only counted FP | Total counted FP | Synthetic H2H wins |
| --- | ---: | ---: | ---: |
| Baseline usable-game strategy | +474.4 | +474.4 | +1.43 |
| Analogue workload, point drafting | +98.3 | +94.6 | +0.07 |
| Analogue workload/rate, point drafting | +76.9 | +84.6 | +0.06 |
| Analogue workload/rate, usable-game drafting | +489.2 | +490.2 | +1.76 |

Draft-only differences use baseline daily lineup forecasts for every policy.
Total differences also use the policy's forecasts for our daily selections.
Minimum three goalie appearances is enforced; bench points are excluded.

The relevant incremental comparison is analogue usable versus baseline usable:
**+15.8 points**, positive in only **5/9 season averages**. Excluding the two
pandemic-shortened target seasons changes that mean to **-8.0 points**. The
incremental synthetic win difference is +0.33, but these correlated and incomplete
matchup samples do not establish a reliable league advantage.

H2H uses the same conflict-free weeks across every policy within each seat/seed,
19-28 weeks depending on the season and affected players. It is a synthetic
round robin, not a reconstruction of Yahoo opponents, matchup dates or playoffs.
Full-season point totals retain flagged provider conflicts. Neither side streams;
this isolates draft and lineup effects from transactions and waiver competition.

## Failure diagnosis

In the worst 2024-25 seat/seed pair, analogue usable finished 953.4 points below
baseline usable. Its goalie choices included Demko and Ingram rather than
Shesterkin and Oettinger. The analogue roster missed the minimum goalie requirement
in 22 weeks, versus one for the comparison roster. The lineups and other skater
picks also differ, so this is evidence of a failure mode, not attribution of the
whole loss to one player or one injury.

This exposes the difference between good mean forecasts and a good roster:
weekly goalie coverage and concentrated availability risk matter. The current
draft utility does not explicitly price the probability of missing the minimum.
It cannot be repaired by declaring a universal number of goalies to draft.
The next candidate should value weekly active-goalie coverage under joint workload
scenarios, then be tested across all years without tailoring it to this failure.

A full-data replay was compared with the cached, roster-filtered fixed replay for
baseline and changed-roster cases. Weekly points, bench totals, appearances and
source-conflict counts agreed. Filtering is used only with fixed rosters; it is
not suitable for streaming because free-agent outcomes would then be omitted.

## First dated goalie-case catalogue

Private labels: `private/goalie-context-cases-2024-v2.json`.
Separate observations: `var/goalie-context-case-outcomes-2025-v2.json`.

Four pilot cases cover a trade, a signing, an editorial role expectation and an
injury concern. They retain NHL IDs, source/publication dates, an explicit
September 13, 2024 research cutoff and unknown numerical start allocations.
Publication dates after that cutoff are rejected. Outcomes are prohibited in the
preseason-label schema and written to a separate, hash-linked artifact.

The cases were chosen retrospectively. Demko was added after inspecting the
failure above and is explicitly labelled as such. Four cases, including two
players sharing a team, are far too few and too selected to train or validate
causal injury/role effects. They establish the data contract for a larger sample.
A reported expectation is not a confirmed coaching assignment or a numeric
start projection. Historical season files also differed in boolean capitalization;
the outcome adapter now handles both forms without treating missing labels as false.

## Reproduction and next work

```sh
uv run python -m research.replay_analogue_drafts --history-dir var \
  --config config.local.toml --output-dir var/NEW-analogue-draft-replay
uv run python research/join_context_case_outcomes.py \
  --cases private/goalie-context-cases-2024-v2.json --history var/history-2025.json \
  --goalie-box snapshots/2026-09-10/sportsdataverse/goalie_box_2025.csv \
  --output var/NEW-goalie-case-outcomes.json
```

All draft picks, weekly scores, analogue neighbors and input hashes remain in
`var/analogue-draft-replay-2026-09-10/`. Current numerical scenario assumptions and
the live draft board are unchanged. The usable-game strategy itself remains a
research comparator, not an automatically promoted live ranker.

Next: build and test weekly goalie-coverage utility, expand the dated goalie
catalogue by a consistent selection rule, and review current risky goalie pairs.
Do not optimize parameters against just the failed 2024-25 draft or claim the
already inspected historical seasons are an untouched holdout.
