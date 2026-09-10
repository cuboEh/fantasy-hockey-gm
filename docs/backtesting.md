# Historical draft experiments

The first experiment is implemented in `fantasy_hockey.backtest`. It is a
research diagnostic, not a validated historical season simulator or a production
model upgrade. The current data permits two chronological draft experiments,
not enough independent seasons to establish a best model.

## Run locally

```sh
uv run python -m fantasy_hockey.backtest \
  --input snapshots/2026-09-10/hockeyinsights/fantasy_2027.json \
  --config config.local.toml --output var/draft-study.json --seeds 5
```

The report includes input/config hashes, all model parameters, every simulated
pick, realized outcomes, missing-result coverage, paired benchmark results, and
rate/total prediction errors separately for skaters and goalies. Runtime reports
are private and ignored by Git. Seeds make synthetic opponent choices reproducible.

## Information boundary and selection

1. For the 2024-25 draft, supply only earlier season observations.
2. Compare eight predeclared combinations: no shrinkage or 20 games of shrinkage
   toward historical positional rates; historical workload or 50% regression
   toward fixed 70-skater/45-goalie appearance assumptions; projected total
   points or positional replacement ordering.
3. Run both 12- and 13-team snake drafts, every seat, with five opponent seeds.
   Compare each policy against the same benchmark and opponent preferences.
4. Choose parameters using only 2024-25 outcomes, on the intersection of complete
   paired scenarios across every candidate model.
5. Lock the winner and evaluate it on 2025-26. Do not search the parameter grid
   against this final season or claim that a losing result is a winning strategy.

The recency decay is fixed at one third per earlier available season. With two
seasons this gives 75%/25%. Position priors use only pre-target historical counts.
The replacement heuristic is the next player beyond league-wide active position
capacity. Bench demand is not estimated in that threshold. Roster feasibility
includes bench capacity, and excludes IR. Only source primary positions are used.

Opponents use the fixed unshrunk historical baseline with seeded persistent
player preference noise of plus/minus 15%. This is a synthetic market, not
historical Yahoo ADP. Every pick is constrained by available roster capacity.
The same player cannot be selected twice. Draft logic receives forecasts, never
realized results. Results are joined after choices have been fixed.

## What the score means

The objective is total NHL-season fantasy production from the entire drafted
roster, including bench players. It is a draft-capital diagnostic. It does not
measure usable lineup points, H2H wins, playoff success, streaming value or
minimum-goalie-appearance compliance. A whole-roster total can overvalue crowded
positions and cannot establish the best policy for this league.

Realized counts include the effect of missed games and changed roles wherever
the source supplies a valid season. Missing season records are unknown, not zero.
Incomplete paired drafts are excluded from paired score comparisons and counted
explicitly. This exclusion itself can bias evaluation, especially for injured or
marginal players. Rate error and season-total error help distinguish production
rate mistakes from availability mistakes, but do not attribute causation.

## Known leakage and limits

The current Hockey Insights file supplies a selected 2026 player pool and current
primary positions. Retired players, missing prospects and historical eligibility
are not recovered by filtering the season column. The source also omits some
low-appearance seasons. No current consensus ranks, trade flags, ages, teams,
MoneyPuck season metrics or future counting stats are used to draft.

The report is labeled `BIASED_CURRENT_POOL_DIAGNOSTIC_NOT_DEPLOYABLE`. Preventing
future-stat access does not remove survivor and metadata bias. Also, 2025-26 was
previously inspected in a rate diagnostic and preliminary engineering runs; it
is not pristine unseen research data. Multiple seeds and seats reuse the same NHL outcomes, so their spread is
not a confidence interval across independent seasons. The experiment never
replaces the live draft board automatically.

## Next requirements for a real season replay

- A complete historical player universe and dated eligibility, retained before
  each simulated draft. Archive the provider's publication and retrieval dates.
- Permitted raw daily scoring components for all relevant players, including
  confirmation of true zero-appearance seasons and complete goalie outcomes.
- Historical schedules and each league week's boundaries. Select daily starters
  with information available before the lineup deadline, then reveal that day's
  outcomes. Do not retroactively start whoever scored best.
- Separate draft, lineup and acquisition policies. Enforce position capacity,
  four acquisitions per week, waiver availability and goalie minimums; define
  opponent waiver behavior explicitly. Weekly outcomes follow these choices.
- Several chronological training/validation seasons and a final untouched season.
  Once a test season informs a change, it becomes development data. Freeze model
  choices before accessing the next test period.
- Compare points, usable games, replacement value and next-pick availability
  against simple baselines. Report paired gains, losses, workload errors and
  sensitivity to opponent behavior, not merely the best trial.

Injury dates and trades should be revealed only when they occurred. Their exact
occurrence cannot be known at draft time, but uncertainty in workloads can be
modeled using pre-draft information. We should judge policies across enough
seasons that one fortunate injury outcome does not determine the model.
