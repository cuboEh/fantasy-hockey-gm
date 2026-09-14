# GM forecast research register

September 14, 2026. P2-FR6/P2-FR7 work in progress. This register extends the
[model design](model-design.md) and [PRD 2.0](../PRD-2.0.md). It records input
readiness and experiment decisions, not evidence that a stronger model exists.

## Coverage audit and decision

One bounded audit inspected the existing normalized 2014-2026 histories, with
638,790 player-game records. All observed stat lines can be scored using the local
league weights. No duplicate player-game identities or invalid team/game links
were found. Source conflicts remain recorded in the audit and need an explicit
handling rule before evaluation.

Unobserved games between a player's first and last appearance are candidate gaps,
not confirmed absences. Do not manufacture zero production or nonparticipation
labels from them. The normalized rows lack ice time, PP time, xG, starter flags,
source observation timestamps, injury status and linemates. Header inspection of
existing raw box scores found ice time and goalie starter fields; existing
MoneyPuck season summaries contain exposure and xG fields. Header presence does
not verify semantics, coverage, joins or dated availability.

Private evidence: `var/prd-2.0/p2/history-input-audit.json` and
`raw-feature-headers.json`. Reproduce the audit with
`uv run python -m research.audit_forecast_inputs --help`; the command records input
hashes, performs no fitting, and refuses to overwrite its output. Tests cover
missing versus explicit nonparticipation, invalid scoring and source immutability.

Decision: develop a transparent observed-game stat-rate baseline first, separately
from participation. Audit raw exposure normalization before attempting role-based
updates. The existing histories have already informed research and cannot be
called untouched test seasons. Any promotion claim needs prospective frozen
forecasts or genuinely untouched outcomes.

## Sources and candidate register

MoneyPuck describes separate pregame, goalie-start and shot-quality models. Its
starter model uses workload/rest and performance inputs, while confirmed starter
reports are distinguished from estimates. Its xG method estimates scoring
probability per shot. These are published implementation descriptions, not our
measured fantasy forecasting results. [MoneyPuck methods](https://www.moneypuck.com/about.htm),
[terminology](https://www.moneypuck.com/glossary.htm), consulted September 14, 2026.

Our design inference is to keep participation, opportunity and production rates
separate before applying fantasy weights. A useful hockey signal does not by
itself establish incremental fantasy forecast accuracy.

| Candidate / user idea | Target and required input | Bounded next decision | Result so far |
| --- | --- | --- | --- |
| Current form and recency | Next-game scoring-stat rates; dated observed games | Compare one fixed recency/shrinkage candidate with a simple expanding-history baseline on identical chronological cases | Completed; rejected as a general replacement, results below |
| Ice time and PP role | Opportunity and scoring rates; dated TOI and PP TOI | Normalize one season first; verify units and player/game joins before expanding | Raw TOI headers found; PP exposure coverage unverified |
| Injuries, trades, linemates and competition | Participation and deployment; dated changes known at forecast time | Validate one sourced change history or retain explicit conditional scenarios | Normalized change history missing |
| Goalie workload and performance | Starts, relief, shot exposure and saves separately; explicit participation and starter observations | Validate raw starter semantics and nonappearance coverage before fitting | Starter header found; reliable absence labels missing |
| NHL plus MoneyPuck, xG and assist composition | Future scoring stats; dated event or game aggregates | Check one as-of join before comparing a single feature addition | Season totals exist; within-season availability not established |
| Age, experience and sparse history | Rate priors; dated biographical and exposure data | Declare sparse-history groups and compare one pooled prior | Deferred until baseline coverage is defined |
| Opponent strength and schedule difficulty | Future per-game rates; opponent features computed before games | Compare one adjustment on the same eligible cases | No experiment run |
| Historical analogues and contextual similarity | Conditional workload/rate changes; reproducible dated cases | Reuse archived evidence, audit leakage and define one additional test | Existing draft studies are development evidence |

Other product-plan ideas remain in the PRD research queue. The first recency
candidate has now been evaluated; see the dated result below.

## Contract for the next comparison

Before fitting, save exact input hashes, development/selection date partitions,
minimum-history eligibility, missing-data exclusions, source-conflict handling,
baseline formula and one fixed candidate formula. Use the same player-game cases
for both. Measure individual-stat MAE and fantasy-point MAE, signed error, coverage
and paired uncertainty grouped by calendar blocks. Report skaters and goalies
separately; report sparse-history exclusions. Observed-game rate evaluation must
not be described as daily workload or matchup forecast accuracy.

Budget: one baseline and one predeclared recency candidate, one chronological
comparison. Stop after reporting positive, negative or inconclusive differences;
do not add variants to obtain a favorable result. Historical evidence may select
a candidate for shadow use, but cannot promote it on these already inspected
seasons. Freeze prospective issue times, workload assumptions, horizons, metrics,
minimum evaluation coverage and promotion/regression thresholds before collecting
promotion outcomes. The dated plan below fixed these formulas and partitions before the one comparison
was run. It supersedes this preliminary contract for that completed trial.

## Completed comparison, September 14

The first bounded comparison is complete. It used histories ending 2024 and 2025
as training context and October 2025 through April 2026 as the chronological
selection period. All are previously inspected development data. Conflicted
player-games were excluded from both training and outcomes. Same-day outcomes
entered history only after every prediction for that date. Minimum conditional
rate coverage was ten prior observed appearances.

Baseline `gm-rates-1`: the player's observed-appearance stat means over the prior
730 days, shrunk toward same-kind pooled means with 20 appearance equivalents.
Candidate `gm-rates-recency-1`: the identical prior and cases, with individual
observations decaying at a fixed 60-calendar-day half-life. There was one candidate,
no parameter search and no second attempt after inspecting results.

| Group | Cases | Baseline point MAE | Candidate point MAE | Candidate minus baseline, paired week interval |
| --- | ---: | ---: | ---: | --- |
| Skaters | 45,924 | 4.321 | 4.383 | +0.049 to +0.077 |
| Goalies, conditional on appearance | 2,640 | 6.825 | 6.777 | -0.083 to -0.009 |

The intervals use 200 calendar-week block bootstrap samples with a fixed seed.
They group shared games and repeated observations within a week; dependence across
weeks remains a limitation. Individual-stat errors, signed point error, sparse
history groups, exclusions and the full prediction ledger are in private evidence:
`var/prd-2.0/p2-comparison/plan.json` and `results/`. The report records source hashes.

A separate diagnostic on 5,086 explicitly listed goalie outcomes reduced Brier
error from 0.2372 to 0.2342 with recency. This is conditional on appearing in the
source's listed cohort. It does not establish daily roster membership or calibrate
current starter probabilities. General daily and matchup workload error remains
unverified without those labels.

Decision: **reject this candidate as a general replacement** under the predeclared
criterion requiring improved paired point errors for both kinds. The modest goalie
result can motivate a separately declared future study; it does not authorize a
post-hoc goalie-only promotion. The candidate remains experimental, and numerical
snapshot validation rejects labeling that version as working. No prediction
superiority or real-roster policy improvement is claimed.

The new GM baseline is available for dated research. Current workload can be
supplied explicitly, or estimated with Beta(1,1) smoothing from a separately
established eligible cohort. Missing cohort membership remains unknown. A dated
external forecast for this historical selection period was not available, so no
external benchmark comparison is claimed. Frozen draft season totals are not
converted into updated remaining-season forecasts.

## Frozen reviews and prospective evaluation

The browser saves the complete input snapshot, calculation, timestamp and state
identity for a reviewed lineup or pickup. `fantasy gm evaluate` compares supplied
outcomes with the earliest saved pre-game forecast for each model/player/game.
Repeated reviews do not multiply the outcome's weight. It rejects duplicate
outcomes, mismatched game times, future outcome observations and nonappearance
rows containing nonzero stats. Reviews frozen after a game started are excluded.

The report separates appearance MAE/Brier, conditional stat/rate error and total
point error, retaining missing forecast/outcome coverage. No evaluation command
promotes a model. Before a future promotion study, declare its outcome window,
minimum cohort coverage, paired baseline, regression limits and stopping rule.
The completed historical comparison cannot supply untouched prospective evidence.
