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

## Context and role assumptions

Represent qualitative context as sourced assumptions about opportunity. A trade
is a fact; losing PP1 is a hypothesis until supported by deployment evidence.
Store source/date, confidence, affected horizon, review/expiry date and whether a
base projection already includes the effect. User overrides remain visible.

Use scenarios for uncertain roles, each with projected total/PP minutes,
appearances and production rates. Combine scenarios using explicit probabilities
and show the range. Initial probabilities are analyst assumptions, not calibrated
model outputs. Stronger linemates can offset reduced minutes. Do not apply both
a scenario change and a separate trade penalty for the same effect.

## Additional candidate metrics, prioritized

These are proposed features and decision metrics, not implemented or validated
predictors. Exact acquisition rights and field availability must be checked.

| Priority | Metric | Purpose |
| --- | --- | --- |
| Before draft | PP ice-time share, not only PP minutes | Separate team PP opportunity from allocation to a player |
| Before draft | Shots/hits per 60 and expected minutes | Separate volume-generating rate from deployment |
| Before draft | Expected appearances and missed-time scenarios | Account for injuries, scratches, uncertain roster spots and rest |
| Before draft | Position/role-conditioned age and experience | Test development/decline priors, especially sparse NHL histories |
| Before draft | Position-specific replacement value | Compare available choices for completing the roster |
| Before draft | ADP, rank tiers and availability at next pick | Distinguish player value from draft acquisition timing |
| Before draft | Projection range and input freshness | Show where rankings depend on uncertain or stale information |
| Early enhancement | Goals versus xG, on-ice shooting percentage | Investigate sustainable finishing and teammate conversion |
| Early enhancement | Individual point participation by strength | Points credited to player divided by team goals while on ice; investigate role/conversion effects |
| Early enhancement | Primary/secondary assist rates | Test differing predictive value without changing scoring credit |
| Early enhancement | Linemate continuity and role competition | Represent promotion/demotion scenarios and dependencies |
| Early enhancement | Team strength and deployment | Test conservative plus/minus and goalie-win adjustments |
| Early enhancement | Goalie start share and shot exposure | Separate quality, workload and fantasy production |
| In season | Feasible lineup capture rate | Assigned eligible games divided by eligible scheduled games under a specified roster plan |
| In season | Marginal points per acquisition | Compare complete legal streaming sequences with the no-move baseline |
| In season | Roster correlations | Simulate shared PP units, teams and goalie tandems consistently |
| Later research | NHL EDGE tracking features | Test incremental predictive value of zone time, shot location and speed |

ADP measures draft behavior, not expected production. Estimate next-pick survival
as an uncertain opponent model, not a guarantee. Multi-position flexibility and
lineup capture are properties of a roster assignment, not fixed player bonuses.
Point participation and on-ice conversion need matching situations/coverage and
small-sample shrinkage; unusual values are not proof of luck or imminent change.

Measure goalie shot exposure jointly with expected stopping performance. With
the user's supplied weights, changing one shot faced from a save to a goal costs
3.6 points before any change to win/shutout outcomes. This is sensitivity to the
scoring formula, not a recommendation to prefer or avoid high-volume goalies.

NHL EDGE publishes skating, shot and zone-time tracking metrics, but fantasy
predictive value and permitted ingestion remain unverified.
[NHL EDGE overview](https://www.nhl.com/news/nhl-edge-launches-website-for-puck-and-player-tracking-data)

Do not add narrative multipliers for contract years, revenge games, motivation
or preseason scoring without evidence of incremental predictive value. Prefer a
small auditable feature set and compare additions with the same held-out baseline.
