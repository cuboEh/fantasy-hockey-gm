# Product goal, MVP and next steps

Revised September 11, 2026. This is the current plan and supersedes older roadmap
priorities. Existing experiments remain evidence, not obligations to keep building.

## Goal

Help Tristan make better draft and roster decisions in his specific Yahoo H2H
points league, by comparing expected usable fantasy production with acquisition
cost, roster constraints and uncertainty, and explaining the tradeoffs.

The intended advantage is practical: buy useful production at better draft prices,
avoid expensive projection mistakes, and generate extra usable production through
active roster management. We seek a measurable advantage over a competent simple
baseline; we have not demonstrated that advantage yet. Winning a particular league
is the aspiration, not a guarantee or a valid single-season model test.

The product is a decision-support tool for an engaged manager. A local CLI,
spreadsheet exports and SQLite are enough. Yahoo read API access would improve
convenience; the core must work with user-supplied data. Automatic roster actions
are a separate future decision, contingent on supported access and terms.

## MVP 1: a useful September 13 draft companion

At any pick, answer: who are my best supported options, why do they fit, what do
they cost relative to Yahoo's market, and what material risk could change that
assessment?

One reviewed board and the existing manual tracker should provide:

- Correct league scoring and user-supplied Yahoo eligibility for reviewed players.
- Historical baseline and selected reviewed projections, with a clear working
  valuation and provenance. Conditional alternatives remain visible and are not
  averaged into a forecast without justification.
- Yahoo rank, preseason ADP, ADP and drafted percentage as separate market inputs.
- Positional tiers or later alternatives that make the cost of waiting inspectable.
  Do not promise a probability of availability from aggregate ADP alone.
- A short list of fitting candidates, current roster needs and concrete explanations.
  Show production/workload, market price, and relevant health/role uncertainty.
- Manual pick entry, undo, saved state, and a spreadsheet fallback.

This is not an autonomous optimal-draft claim. The current deep-search planners
are optional experiments, not required for MVP completion. A dependable board
and transparent shortlist are more valuable than an elaborate unvalidated search.

### Done means

1. The reviewed Yahoo identities/eligibility are incorporated into a new dated
   working board/session. The current live session and original inputs are preserved.
2. High-priority draft targets have defensible estimates or explicit watchlist
   treatment. Unprojected players remain searchable but are not assigned invented
   values or silently recommended. Missing fringe players do not block release.
3. The two identified team conflicts are resolved for any affected recommendation,
   or those players retain an explicit conflict restriction until resolved.
4. The shortlist is legal for the configured roster, updates when picks are entered,
   and explains its valuation and risks. It makes no unjustified early-goalie rule
   or blanket positional ordering assumption.
5. One end-to-end rehearsal of this exact working board/session verifies pick entry,
   undo, recovery and exports. Reuse previous tests; do not rerun every experiment.
6. The actual draft slot is set when known, and the guide describes a simple
   draft-day workflow. The draft time is still needed for operational planning.

Current state: scorer, comparison, tracker, schedule logic and conditional scenarios
exist. Yahoo's supplied table contains 390 matched identities and 264 ADP pairs;
125 eligibility differences are reviewed in the comparison but not yet merged into
the live tracker. There are 52 missing baseline estimates and two team conflicts.
The product is therefore close in mechanics, but not yet a finalized draft board.

## Ordered pre-draft work

1. **Resolve input problems that change picks.** Address the Evangelista/Tolvanen
   team conflicts, integrate the reviewed Yahoo eligibility, and prioritize missing
   players with early ADP or high drafted percentage. Keep source statuses dated.
2. **Choose and document the working valuation.** Compare a permitted independent
   preseason projection export if available. Audit the largest material differences
   from our baseline, especially workload/role changes and rookies. Do not make a
   new external subscription or API a requirement for the MVP. If a credible input
   cannot be obtained, expose the limitation and use a conservative supported case.
3. **Finish the practical shortlist.** Connect that valuation and Yahoo market data
   to the existing draft guide. Show position-specific alternatives and avoid
   treating rank gaps as proven bargains. Keep scoring fit distinct from market price.
4. **Freeze and rehearse the draft deliverable.** Save the dated board/configuration,
   create the reviewed session, export the spreadsheet, and verify the actual
   workflow once. After that, refresh material news/inputs rather than redesigning.

An independent projection baseline can be pursued alongside input review, but no
batch of simulations should precede a clear decision about what it would change.
We do not need to fill every missing low-demand player before the draft.

## MVP 2: weekly roster opportunity after the draft

Return to the original first-useful-milestone idea: `fantasy analyze-week` should
show league/team context, the roster, games remaining, usable games and schedule
congestion, then explain obvious lineup and roster-slot opportunities. This command
is planned, not claimed to exist today.

Start with user-supplied roster/availability data; use supported Yahoo reads if
approved. Evaluate today and the current matchup first. Keep next 7/14 days and
rest-of-season estimates separate as those horizons are added.

Then recommend legal adds/drops and streams within four weekly acquisitions,
Daily-Today locks and confirmed waiver rules. Include the player lost, opportunity
cost, expected usable production, and goalie qualification. Count relief appearances
separately from starts where supported. Matchup dates, waiver type and waiting
period remain inputs to verify, not assumptions to hide.

Done means a recommendation can be checked against the actual roster and calendar,
explains its expected benefit and cost, and can be executed manually. A four-game
player on full roster nights must not automatically beat a three-game player with
three usable games. Recommendations need not require a probabilistic optimizer.

## How we assess usefulness and advantage

Product reliability and predictive edge are different tests:

- Reliability: correct identities/scoring, legal lineups, working persistence,
  understandable advice, and visible missing data.
- Draft quality: compare against simple league-scored and market-following choices,
  under the same eligibility, roster rules and uncertain opponent behavior.
- Management quality: compare against the same drafted roster with straightforward
  active-lineup management, so streaming value is not confused with draft quality.
- Forecast quality: retain dated predictions and measure workload and rate errors
  separately when outcomes arrive. Preserve the existing prospective snapshot.

Report both production and weekly outcomes, along with missed goalie minimums,
transaction usage and variation across seasons/seeds. Synthetic all-play is a
useful diagnostic, not a league-win probability. Historical seasons already used
for development are not untouched holdouts. Realized results from one managed
team cannot alone establish the counterfactual value of each recommendation.

## Deferred idea: schedule strength and opponent-specific opportunity

Recorded from Tristan on September 11, 2026. Relevant to both MVPs, but explicitly
not a current implementation priority. All active development remains focused on
completing MVP 1. Existing schedule/usable-game functionality remains available;
this idea adds opponent context rather than replacing that work.

Use the published 2026-27 NHL schedule to examine:

- Easier or harder stretches of opponents over a week, month or other horizon.
- Draft choices and waiver pickups whose upcoming games offer better opportunity.
- Fantasy playoff schedules, including opponent quality, game volume, off nights
  and whether those games fit the actual roster and league playoff dates.
- Repeated matchups within a month and player performance against particular teams.
- Differences between a short-term scheduling advantage and rest-of-season value.

When revisited, distinguish known schedule facts from uncertain forecasts of
opponent strength. Investigate whether individual player-versus-team history
predicts future performance after accounting for sample size, role/team changes,
and broader player and opponent quality. Treat it as a hypothesis, not an automatic
bonus based on a few memorable games. Use only information available at the time
of each decision when evaluating it historically.

Potential future output: explain a pickup's usable games, upcoming opponents,
estimated opponent adjustment, and the cost of dropping the current player.
Avoid counting schedule benefits twice if they already enter projected production
or usable-game value. Refresh schedule data when fixtures change.

Return to this after the core draft companion is complete, during weekly/waiver
planning or a later playoff-planning increment. No new implementation or research
is authorized as the immediate priority by this note.

## Parked until justified

Full-draft and two-turn search refinements, new Monte Carlo/category-win models,
learning weights from repeatedly inspected seasons, broader automated news ingestion,
trade analysis, notifications and automated roster writes. Category-balancing logic
is not a priority for the current points league. No Docker, web application, cloud
services or new infrastructure is needed for these MVPs.

Before adding code or spending substantial compute, state the user decision it
improves, the input that supports it, the smallest implementation, and the test that
could show it failed. Existing work is retained when reusable, not expanded merely
because it was expensive to build.
