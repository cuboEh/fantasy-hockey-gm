# Fantasy Hockey GM: PRD 1.1

**Date:** September 13, 2026
**Theme:** Complete draft-decision support and an unattended server handoff
**Status:** Draft scope, not activated or implemented

PRD 1.0 delivered a working, traceable guide. This bounded follow-up makes its
remaining decision limits easier to act on before the draft. League-scored
statistics remain primary. A more polished explanation does not establish a
predictive advantage or make a speculative workload reliable.

## Scope summary

| Phase | Focus | Status |
| --- | --- | --- |
| P1 | Compare the suggested and points-first plans under stress | TODO |
| P2 | Inspect the cost of final-pick goalie coverage | TODO |
| P3 | Compare a manager-selected player | TODO |
| P4 | Refresh evidence and prepare draft targets | TODO |
| P5 | Rehearse, package and hand off the release | TODO |

## P1: Inspect a close call

> The manager should see whether the suggested plan's projected lead survives
> the existing stress cases, including gaps in the evidence for either plan.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P1-FR1 | For each tested opponent case, the guide shows the suggested plan and points-first plan's projected lineup values under both working forecasts and conditional stress. | TODO | Reuse fixed-pair branch values; keep the selected later player fixed under stress. |
| P1-FR2 | Each comparison shows the signed suggested-minus-points-first difference for both forecast cases. | TODO | Same roster, horizon and opponent case on both sides. |
| P1-FR3 | Each plan identifies which selected players lack an individual stress assessment. | TODO | Include later players when applicable. Missing stress is not low risk. |
| P1-FR4 | When the suggested plan's lead reverses or becomes a tie under stress, the explanation explicitly identifies that result. | TODO | No invented probability or arbitrary meaningful-gap threshold. |

Acceptance: use the saved early, middle and final states from PRD 1.0 plus an
illustrative exact tie. Reconcile each difference with the fixed-pair values.
Verify that asymmetric stress coverage is visible and never labeled safer by
default. No parameter fitting or new opponent simulation campaign.

## P2: Final-pick goalie coverage

> Another goalie can protect usable goalie production but costs a roster place.
> The manager needs to see that tradeoff alongside the ordinary recommendation.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P2-FR1 | Before the final roster place, the dashboard states that the ordinary comparison does not assess weekly goalie qualification. | TODO | Reminder only; no forced early-goalie rule. |
| P2-FR2 | With one roster place left and the manager on the clock, a separate goalie-coverage comparison is available when supported start and rate inputs are configured. | TODO | Reuse compare_working_completion; no broader draft search. |
| P2-FR3 | The comparison shows each final-pick option's usable skater points, qualified goalie points and total under the baseline and downside cases separately. | TODO | Do not add qualification-adjusted goalie value on top of ordinary goalie points. |
| P2-FR4 | The comparison shows the signed total-point cost or benefit of selecting a goalie instead of the best supported skater in each case. | TODO | If no supported skater fits, state that the reference is unavailable. |
| P2-FR5 | Each option's failed-calendar-week estimate is labeled a conditional proxy using unverified matchup boundaries and excluding relief appearances. | TODO | No claim of actual Yahoo qualification probability. |
| P2-FR6 | Missing, incompatible or unsupported coverage inputs produce an explicit reason while ordinary comparison and tracking remain usable. | TODO | Do not infer starts from projected appearances. |
| P2-FR7 | A pick, undo, slot change or eligibility correction invalidates previously displayed coverage advice. | TODO | Apply existing stale-state protections to the new view. |

Acceptance: reuse the saved final-pick states at seats 1, 7 and 14 from the existing
coverage audit. Compare displayed results to the existing calculation. Exercise
missing inputs, no fitting skater, premature use and stale advice. Verify ordinary
tracking still works after each unavailable comparison. Read inputs separately
from pure calculations; retain the ordinary guide as the fallback.

## P3: Compare a manager-selected player

> The manager may have a target outside the generated shortlist. The tool should
> evaluate that choice under the same rules instead of forcing the manager to
> trust only the names the shortlist happened to include.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P3-FR1 | The manager can select an available player from search for a comparison without recording a draft pick. | TODO | Keep compare and record actions distinct. |
| P3-FR2 | A selected supported, fitting player is included beside the suggested and points-first choices even when outside the automatic shortlist. | TODO | Reuse the bounded comparison with an explicit candidate; no all-pairs search. |
| P3-FR3 | The selected player's comparison uses the same roster, horizon, opponent cases and fixed-pair stress rules as the baseline comparison. | TODO | Do not independently cherry-pick favorable opponent cases. |
| P3-FR4 | A selected unsupported, unavailable or non-fitting player displays the exclusion reason instead of an invented comparison value. | TODO | Tracking remains available. |
| P3-FR5 | Changing the selected player or draft revision prevents the prior selection's advice from being displayed as current. | TODO | Include selected identity in cache identity. |

Acceptance: select a supported player outside the ordinary shortlist and reconcile
its results with the existing calculation. Exercise drafted, unsupported and
non-fitting selections. Verify no pick is recorded by comparison and that selection
changes cannot reuse the wrong cache entry. Inspect desktop and narrow layouts.

## P4: Evidence refresh and draft targets

> Spend research effort on players likely to change a real decision and produce
> a short reference the manager can use without reading a long research report.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P4-FR1 | The existing priority-player review queue has dated source-linked refresh notes identifying material changes or unresolved questions. | TODO | Start with the seven players in the September 11 refresh. |
| P4-FR2 | Any revised working forecast exposes the numerical change and supporting evidence separately from its unchanged historical comparison. | TODO | No numerical change is required when evidence does not justify one. |
| P4-FR3 | A target sheet presents at most 20 middle/late-market players with league-scored season points, projected workload, Yahoo eligibility, market price, and review date. | TODO | For this sheet, supplied ADP above 42 defines the market pool; missing ADP is explicitly unclassified. This is not a guarantee of draft-round availability. |
| P4-FR4 | Each target has a named positional alternative and a numerical production/price tradeoff using the same working forecast. | TODO | Raw season differences are not roster-specific usable-point gains. |
| P4-FR5 | Target notes state material workload/role uncertainties or missing assessments instead of assigning an unsupported upside score. | TODO | Rank gaps alone cannot justify bargain labels. |
| P4-FR6 | Targets without a supported working projection appear only in a separate watchlist section with missing-data reasons. | TODO | Do not assign zero value or silently recommend them. |

Acceptance: prioritize the seven already reviewed players, then at most 13 additional
players surfaced by saved comparisons, market disagreement or the supplied watchlist.
Deduplicate sources and avoid treating one repeated story as independent evidence.
Verify current facts through permitted dated sources. Audit each target-sheet number
against the same board. Publish detailed player notes only to ignored local output.

## P5: Release rehearsal and morning handoff

> The overnight output must be usable in the morning with little manager attention,
> including a recovery path if an optional feature remains unfinished.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P5-FR1 | The offline spreadsheet matches the reviewed session's valuations, eligibility and restrictions. | TODO | Preserve prior snapshots and exports. |
| P5-FR2 | Reopening a backup of the reviewed session restores its picks, roster and settings. | TODO | Never replace the actual draft session with practice state. |
| P5-FR3 | A short handoff identifies the verified release, launch command, input review date, fallback files and unresolved operational questions. | TODO | Slot 4 is saved but has not been confirmed as the actual assignment. |
| P5-FR4 | The handoff identifies completed, incomplete and blocked requirements with their actual verification evidence. | TODO | Unavailable browser tooling does not certify visual acceptance. |
| P5-FR5 | An optional feature with missing inputs leaves the ordinary board and manual tracker usable. | TODO | Exercise each failure path introduced by P1-P4. |

Acceptance: run the required tests and one bounded browser rehearsal of changed
behavior using saved early/middle/late/final states. Verify launch from a fresh
server checkout, backup recovery and the spreadsheet. Produce a morning handoff
short enough to read in a few minutes. Record input and source hashes privately.

## Delivery boundaries

Implement and verify one phase at a time. Each phase must stand on its own so
an incomplete later phase cannot disrupt the verified PRD 1.0 guide. Do not
activate a partially tested coverage view for the real draft. Run the required
unittest suite for scoring changes and browser checks for changed interactions.
Stop expanding scope once these acceptance checks pass.

No new optimizer, fitted risk score, breakout model, exhaustive permutations,
full-draft Monte Carlo, historical data repair, streaming or schedule-strength
model in this increment. No Yahoo automation or roster writes. Do not count
simulated gains as independent validation. Keep private artifacts ignored.

Implementation pointers belong in Notes; the observable requirements above are
the acceptance contract. Upon activation, archive the completed PRD 1.0, move
this document to the docs root, and update the active pointer and inbound links.
Until then, the [completed PRD 1.0](../PRD-1.0.md) remains the delivery record.

## Overnight execution and bounded PRD chaining

The user requested an extensive overnight queue and a follow-up topic on September
13. The following defines that queue; it does not grant access to another machine,
publish permission, or unlimited model usage. See the [server runbook](../reference/overnight-server.md).

1. Before launching unattended, verify the private checkout, required ignored inputs,
   authentication, Python/uv, and local browser tooling. Record an absolute stop time
   in `var/overnight/run-plan.md`. If no time budget is supplied, propose six hours
   as a starting configuration rather than assuming all time until the draft is free.
2. Activate this PRD on a dedicated development branch. Execute P1-P5 in dependency
   order. Continue routine implementation without repeated user confirmation. If an
   input blocks one FR, record it and continue independent authorized requirements.
3. Before an expensive run, name its decision, cases and stopping rule. Use the four
   saved draft stages first. Expand only to resolve a specific failure. Never fit
   forecasts to preferred player names or repeat tests merely to consume the night.
4. Update FR evidence and a resumable `var/overnight/progress.md` after each increment.
   Record exact commands, failures and next action. Make local checkpoint commits
   containing reviewed code/docs/tests only. Do not push, merge, deploy or overwrite
   the actual draft database during this unattended run.
5. After PRD 1.1 is fully verified, save its release checkpoint and handoff. If at
   least 90 minutes remain before the stop time, create and refine **PRD 1.2:
   Read-only post-draft roster audit**. This is the one permitted automatic successor.
6. PRD 1.2 may implement an audit of a supplied roster: positional gaps, supported
   forecast coverage, goalie-review availability, and next-seven-day scheduled versus
   usable games using the existing slot matcher. Accept a supplied as-of date. No
   waiver recommendations, transactions, inferred actual roster, unverified goalie
   start conversion, new forecast training or opponent-strength model. Verify with
   labeled illustrative rosters if the real post-draft roster is not available.
7. PRD 1.2 must have its own numbered FRs and acceptance cases before code changes.
   Reuse existing schedule/roster functions. Implement on a separate branch or
   worktree so unfinished follow-up work cannot compromise the PRD 1.1 checkpoint.
   Do not create PRD 1.3 in this run. If less than 90 minutes remain, write only the
   PRD 1.2 draft and include it in the handoff.
8. Reserve the last 45 minutes for verification, checkpointing and handoff, not new
   features. A hard process timeout is a backstop, not the primary checkpoint method.
   Mark incomplete requirements honestly. If required input/auth/tooling remains
   unavailable after one focused setup attempt, stop retrying that dependency and
   complete independent work. End when the queue is done or the stop time is reached.

Morning handoff: release branch/commit, completed FRs, actual test results, remaining
limitations, source-review cutoff, exact launch/fallback paths, and no more than
three manager actions. Distinguish the verified draft release from any post-draft
prototype. Do not claim model improvement solely because more work was completed.
