# Multi-source fantasy model

Proposed September 10, 2026. This is the next model design, not a trained model.

## Source responsibilities

- NHL records, obtained through a permitted source: observed production, games,
  appearances, ice time and schedule history.
- MoneyPuck published downloads: chance quality, adjusted expected goals and
  shot-quality context for goalie performance.
- Yahoo, when access is approved: fantasy eligibility, league rules, roster
  ownership, availability, locks and authoritative fantasy scoring outcomes.
- Our model: future appearances, production, uncertainty and roster-slot value.

Store raw observations, derived features and predictions separately. For every
value preserve provider, units, season, situation, observation time and model
version. Reconcile conflicting raw counts against the authoritative source;
never average two vendors' versions of the same recorded goal total.

Join using validated external-ID crosswalks, season, competition type and
situation. A MoneyPuck `playerId` is a candidate match to NHL `playerId`, not
permission to skip identity checks. Season-start year 2025 maps to NHL season
20252026, not calendar year 2025. Trades and all-team totals require deduplication.

## Project production before applying scoring

For a points league, expected points equal the scoring-weighted sum of expected
stat amounts. Independence is not required for this expectation, but correlations
matter for uncertainty and later matchup-win probabilities.

MoneyPuck features should inform those predicted amounts. Do not add an arbitrary
MoneyPuck bonus after converting them into fantasy points. Keep a separately
labeled analytical profile if the user wants to inspect player quality metrics.

Candidate feature groups to test:

| Group | Proposed use |
| --- | --- |
| Historical shots, hits, goals, assists, plus/minus and PPP | Transparent rate baseline |
| Games and situation-specific ice time | Project exposure separately from production rate |
| Individual xG and shot quality | Test improvements to future goals estimates |
| Flurry/venue-adjusted xG | Alternative correlated features, not additive bonuses |
| Primary/secondary assists and PP usage | Test assist and power-play production estimates |
| Goalie xGA and actual GA | Derive GSAx with matching coverage, test future performance |
| Goalie workload and team context | Estimate appearances, shot exposure and wins |

MoneyPuck's [methodology](https://moneypuck.com/about.htm) and
[glossary](https://moneypuck.com/glossary.htm) distinguish ordinary xG from
shooting-talent adjustment, individual metrics from on-ice percentages, and
goalie goals saved above expected from raw save percentage. These are distinct
features with different purposes, not one universal fantasy rating. Download
availability must be verified for each desired feature; webpage visibility alone
does not establish downloadable access.

## Incremental experiments

1. Baseline: recent historical per-game rates blended across multiple seasons,
   with small samples pulled toward a relevant position/role average. Separate
   projected appearances from per-appearance production. Record assumptions for
   rookies, injuries, role changes and players without sufficient history.
2. Enhancement: predict individual scoring stats using a small, regularized
   feature set including MoneyPuck information. Start with goals and goalie
   performance rather than expecting xG to improve every category.
3. Comparison: evaluate any permitted external projection as another baseline.
   Blend predictions only if chronological validation supports it.
4. Optimization: translate projected stats into points, then compare complete
   feasible rosters, replacement options, draft availability and horizon-specific
   usable games. Expected season totals are an input, not the final draft policy.

Avoid double-counting all-situation and strength-specific totals. Power-play goals
already count as goals and can additionally earn PPP points under configured
rules; do not apply another role bonus for the same predicted production.

## Evaluation and limits

Train on older periods, tune on later validation periods, and reserve subsequent
periods for testing. Compare raw-stat-only and MoneyPuck-enhanced models on the
same players, periods and exposure assumptions. Measure stat error, fantasy-point
error, ranking usefulness and resulting draft/roster outcomes. Report missing
players and coverage rather than evaluating only convenient complete records.

Historical xG files can reflect provider models revised after the target period.
Record that limitation or use contemporaneous model versions where available;
chronological game timestamps alone do not eliminate all retrospective leakage.
Never use a final season's features to forecast the start of that same season.

Before draft day, prefer an auditable baseline with explicit uncertainty over an
unvalidated complex model. Goalie shutouts and single-game results need broad
uncertainty. Higher NHL analytical quality does not necessarily imply higher
fantasy value under the league's weights, roster slots and player availability.
