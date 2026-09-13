# Fantasy Hockey GM: PRD 1.0

**Date:** September 12, 2026
**Theme:** A credible statistical reason to pick beyond the next name
**Status:** Complete, September 12, 2026. Useful-guide acceptance passed; predictive advantage remains unproven.

The manager needs a dependable recommendation during the September 13 draft,
especially when middle- and late-round players have less certain production.
League-scored projections lead. The guide must explain when another available
player offers a supported advantage over the highest projected scorer who fits
the roster, and when taking that obvious pick is the best supported choice.

This is an incremental acceptance contract for the existing tool. TODO means
verification or implementation remains, not that the capability must be rebuilt.
The operational MVP and previous studies remain documented in the
[product plan](product-plan.md), [comparison notes](guides/pick-comparison.md) and
[validation report](archive/validation-2026-09-11.md).

## Scope summary

| Phase | Focus | Status |
| --- | --- | --- |
| P1 | Statistical basis and explicit baseline | Done |
| P2 | Explain the pick and the cost of waiting | Done |
| P3 | Uncertainty and supported opportunity | Done |
| P4 | Draft-day acceptance | Done |

## P1: Statistical basis

> The manager can identify the statistical basis of a recommendation and compare
> it with a consistent, understandable default choice.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P1-FR1 | Each on-clock comparison identifies the available, supported, roster-fitting player with the highest projected season points as its points-first baseline. | Done | Four saved states pass legality/max-points checks; baseline names verified in browser comparisons. |
| P1-FR2 | Each compared player shows projected season fantasy points calculated with the configured league scoring. | Done | 38 candidate entries reconcile with configured scoring; 24 visible cards verified in browser. |
| P1-FR3 | Each compared player exposes the projected appearances and per-appearance fantasy production underlying the season estimate. | Done | API, cards and CLI expose appearances/rate; browser values match comparison payloads. |
| P1-FR4 | Each compared player exposes the source and date of the working projection. | Done | Original source/date displayed in browser; absent and partial evidence use unavailable fallbacks. |
| P1-FR5 | Historical statistics and conditional scenarios are labeled separately from the working projection. | Done | Browser details separately show working forecast, historical comparison and earlier analyst cases. |
| P1-FR6 | Players without a supported working projection remain searchable with the reason they cannot be recommended. | Done | Browser search finds unsupported players with watchlist toggle off; details show missing-projection and eligibility reasons. |

## P2: Explain the choice

> A recommendation earns a departure from the default through a numerical
> comparison the manager can inspect, including what may remain at the next turn.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P2-FR1 | The recommendation summary names the suggested pick alongside the points-first baseline, explicitly stating when they are the same player. | Done | Browser verified same-pick wording in early state and named alternatives in middle, late and final states. |
| P2-FR2 | A different suggested pick shows its signed season-point difference from the baseline. | Done | Signed season-point differences reconcile with both candidates; verified in browser and CLI. |
| P2-FR3 | The guide shows the signed difference in projected added lineup points between the suggested plan and baseline plan over the same pick horizon and opponent cases. | Done | All 38 candidates reconcile across the same horizon/cases; signed plan differences shown in browser. |
| P2-FR4 | For each compared first pick, the manager can inspect the selected later player and pair value in each tested opponent case. | Done | All compared candidates now visible; 116 paired opponent-case comparisons checked in browser. |
| P2-FR5 | A recommendation that differs from the baseline explains its benefit using the displayed lineup contribution or later-alternative comparison. | Done | Now/later contribution differences sum to total advantage; regression fixture and saved states pass. |
| P2-FR6 | If no alternative exceeds the baseline's compared lineup value, the guide retains the baseline, including exact ties. | Done | Exact tied pair retains points-first despite opposing ID order; regression test passes. |
| P2-FR7 | Market rank and ADP appear as distinct price context, with missing values explicitly labeled unavailable. | Done | Distinct Yahoo rank/ADP visible; real missing ADP and illustrative missing rank/ADP display unavailable. |
| P2-FR8 | At the final pick, the comparison describes one-pick value without inventing a later selection. | Done | Final-pick button, summary, cards and CLI use one-pick language; no later selection is rendered. |

## P3: Uncertainty and supported opportunity

> Later-round opportunity deserves consideration when evidence supports it.
> Uncertainty must remain visible rather than silently becoming extra points.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P3-FR1 | A player-specific role or workload case exposes its dated evidence and numerical assumption separately from the working projection. | Done | Browser displays case date/source, conditional roles or start assumptions, dated evidence and review history separately from forecasts. |
| P3-FR2 | The guide labels a recommendation assumption-sensitive when a compared opponent or supported stress case prefers another first pick. | Done | Sensitive flag and alternative/shortfall per case verified against four saved states and regression test. |
| P3-FR3 | A player without an individual stress case is labeled as lacking that assessment. | Done | Browser explicitly labels absent individual stress as unassessed; no-stress regression passes. |
| P3-FR4 | The comparison states that tested opponent survival counts are scenarios, not availability probabilities. | Done | Browser scenario counts and sensitivity explanation explicitly reject availability/win-probability interpretation. |
| P3-FR5 | Every reported advantage is labeled projected rather than proven future performance. | Done | Summary, cards and sensitivity differences labeled projected; no proven-performance claim. |

## P4: Draft-day acceptance

> The manager can act on the explanation during the draft and recover from
> tracking mistakes without losing the trusted board.

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P4-FR1 | Recording a pick removes that player from available recommendations. | Done | Browser practice pick removes selected player from available pool and recommendations. |
| P4-FR2 | Undo restores the previous available pool and invalidates advice from the undone state. | Done | Browser undo restores identical pre-pick pool and clears comparison. |
| P4-FR3 | A slot, eligibility or pick change prevents advice from the old state being presented as current. | Done | Browser slot and eligibility corrections clear advice; stale API requests rejected; automated regression passes. |
| P4-FR4 | An unavailable comparison displays its reason while ordinary manual tracking remains usable. | Done | Browser unknown-slot, off-clock and missing-owned-forecast reasons verified; manual tracking still succeeds. |
| P4-FR5 | Reopening a saved practice session restores its recorded picks and roster. | Done | Browser reload preserves picks/roster/pool; downloaded SQLite backup reopens to identical board. |
| P4-FR6 | A spreadsheet fallback exposes the frozen board's valuations and source limitations. | Done | Frozen and freshly exported CSV each contain all 513 identities with matching rounded valuations, explicit blanks and restrictions. |

## Acceptance cases and release gates

Before implementation, select saved practice states for early (rounds 1-3), middle
(4-10) and late (11-16) draft stages. Use at least one state per stage and include
the final pick. Record their input identities in ignored local evidence. These
are usability/consistency checks, not independent predictive validation.

Exercise both an obvious pick retained and a supported alternative preferred.
Use small illustrative fixtures if saved states lack exact ties, missing forecasts,
or an assumption-sensitive choice. Label fixtures illustrative. Expected behavior
comes from the stated rules, never a preselected real player's name. Verify the
displayed differences against the underlying comparison for all selected states.
Inspect the local dashboard manually and rehearse pick, undo, reopen and fallback
in an isolated session. Record observed results against FR IDs.

**Useful guide gate:** every FR is verified Done with evidence. Any failure remains
visible and prevents claiming this PRD complete. The gate passed September 12 after implementation and verification of all phases.
Writing the requirements alone did not establish acceptance.

**Predictive advantage gate:** separate future validation against points-first and
market baselines on sufficiently complete independent outcomes. Not a requirement
to finish this pre-draft release, and not established by mock projected gains.

## Scope limits

No new optimizer, exhaustive full-draft search, fitted breakout score, automatic
news ingestion, streaming model or historical data repair in this increment.
No blanket early-goalie or contrarian-pick rule. No arbitrary numerical threshold
claiming that a small lead is statistically meaningful. Sensitivity is exposed
through P3; uncertainty intervals require evidence the current model does not have.
Future work stays in the product plan. The actual draft slot remains an operational
input when known, not a blocker to isolated rehearsal.

## P1 implementation evidence, September 12

The comparison now carries projected appearances, FP per appearance, original
forecast evidence, historical comparison and conditional review separately.
Dashboard comparison cards expose these fields; watchlist details state the
exclusion reason. The working comparison CLI identifies the points-first baseline
and prints workload, source and projection date. Valuation weights are unchanged.

149 unit tests passed, including two new regression cases for provenance isolation
and exclusion of an unsupported high scorer. Four preselected saved practice states
at early, middle, late and final picks passed checks for baseline legality and
maximum season points. All 38 compared candidate entries reconcile with configured
league scoring and appearances times rate. No new drafts or tuning runs were used.

Local evidence: `var/prd-1.0-p1-2026-09-12/` contains input hashes, selected states,
comparison outputs, verification summary and test log. No live session was changed.
The user subsequently authorized local browser verification. P1 passed actual
browser checks across all four isolated sessions: 24 visible comparison cards
matched their payloads for points, workload, source/date and separate historical
comparison. Missing/partial provenance fallbacks were exercised with illustrative
in-page objects; real watchlist search exposed missing projection and eligibility
reasons with the watchlist toggle off. Earlier analyst cases remained distinct.

Browser inspection found and fixed long source URLs overflowing adjacent cards
and unchanged periodic refreshes collapsing open details. Desktop and 390-pixel
mobile inspection now show wrapped evidence without overflow. An unchanged refresh
retains expanded details; recording a practice pick clears stale advice and undo
restores the previous pick. No console errors or warnings were observed. JavaScript
syntax and whitespace checks passed. Browser payload checks are retained in
`var/prd-1.0-p1-2026-09-12/browser/render-checks.json`; screenshots were inspected
in the verification session. P1 is complete; P2-P4 remain unverified.

## P2 implementation evidence, September 12

Recommendations now name the suggested pick and points-first alternative, show
signed season-point and projected lineup differences, and split the latter into
current-pick and later-selection contributions. Each opponent case exposes both
selected pairs and their signed value difference. All compared candidates are
inspectable. Exact plan ties retain the points-first baseline. Market rank and
ADP stay separate, with explicit missing values. Final-pick presentation uses
one-pick values without a fictitious later choice. No projection weights changed.

152 tests passed, including new cases for the explanation accounting, exact ties,
final-pick behavior and missing market data. Reused the four P1 practice states;
all 38 candidate deltas reconciled, with no new draft campaign or tuning. Browser
checks verified all 38 displayed cards and 116 paired opponent-case comparisons,
including an obvious pick retained and alternatives preferred. Desktop (1440px)
and mobile (390px) screenshots were inspected without horizontal overflow. The
final-pick CLI was exercised as well. No application JavaScript errors occurred;
the browser requested an absent favicon (404), recorded as a cosmetic follow-up.

Local evidence: `var/prd-1.0-p2-2026-09-12/` contains four comparison outputs with
input hashes, numerical and browser checks, test log and final-pick CLI output.
The practice servers used P1's isolated databases; live draft state is untouched.
P2 is complete. P3 uncertainty presentation and P4 release rehearsal remain.

## P3/P4 release evidence, September 12

The recommendation now names assumption-sensitive cases, their preferred first
pick and projected shortfall. Strict case comparisons drive this label; it is not
a probability or a new forecast adjustment. Conditional review dates, source,
role labels, earlier goalie start assumptions and dated evidence are exposed
separately. Review history is preserved. Unassessed players remain explicit.

156 tests passed, including new sensitivity/no-stress, eligibility/slot invalidation
and missing-owned-forecast tracking cases. Four saved states were checked without
new full-draft simulations: middle/final choices were sensitive; early/late choices
were stable across the tested cases. Desktop and 390px mobile browser inspection
verified the explanation, dated workload evidence and missing-stress labels.

The isolated browser rehearsal verified pick removal, undo restoring the exact
available pool, reload persistence, slot-change invalidation, eligibility-change
invalidation and rejection of stale comparison requests. Corrected eligibility
changed the compared shortlist as expected. Unknown slots, off-clock turns and
missing owned forecasts displayed explanations while manual tracking remained
usable. The downloaded SQLite backup reopened to the identical board and roster.
Both the frozen and regenerated CSVs matched all 513 identities and rounded
valuations, retaining blank missing values and recommendation restrictions.

Local evidence: `var/prd-1.0-release-2026-09-12/` contains comparison outputs,
verification report, test log, isolated databases, downloaded backup, CSV fallback
and final-pick CLI check. The live database's before/after hash is identical.
JavaScript syntax and whitespace checks passed. Expected rejected requests and
an absent favicon can produce HTTP errors; no application script exception was
observed in the completed checks.

All 25 FRs are Done. This establishes a usable, traceable guide under the current
inputs, not a validated predictive advantage. Confirm the real slot and refresh
material draft-day evidence through the existing workflow. Broader research remains
outside this completed release.
