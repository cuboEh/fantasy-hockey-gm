# Contextual scenarios: first player-specific pilot

The pilot covers three skaters and Minnesota's shared goalie workload. It tests
explicit deployment and recovery hypotheses instead of simply adding or
subtracting ten games. Every case separates a dated reported fact from our
numeric assumptions, records what would confirm it, and has a review date.
It is research output, not a replacement for the live board.

## What the cases change

| Case | Mechanism | Remaining uncertainty |
| --- | --- | --- |
| Tkachuk | Shot volume, scoring conversion, assists and PPP change separately; appearances/hits held fixed | Actual linemates, PP usage and numerical effects remain unconfirmed |
| Barkov | Separate season availability from an initial phase at reduced offensive rates | Camp workload and effectiveness after returning |
| Jarvis | Early missed team games, subsequent availability and a post-return phase | Return window is not mapped to a verified upcoming schedule |
| Minnesota goalies | Joint start allocation, reserve starts, and separate start/relief scoring rates | Recovery, rotation, reserve role and repeatability of prior rates |

There is no independent generic role adjustment on top of the stat changes.
PPP must remain within goals plus assists. Missed games replace historical
appearance assumptions rather than being deducted from already reduced GP.
Goalie starts, including reserves, must sum to 84. Relief appearances are
additional appearances, not additional team starts.

The lower/middle/higher cases have no assigned probabilities. The middle case is
not automatically the most likely. Numerical percentages and start allocations
are analyst judgments, not quantities supplied by news reports. Reporting
supports exploring a mechanism; it does not establish its exact effect size.

## Results and interpretation

Private output: `var/context-pilot-2026-09-10-v3.md`, with full stat deltas,
parameters, baseline comparisons and provenance in the adjacent JSON.

- Tkachuk: roughly 739-805 whole-player fantasy points in the specified role cases.
- Barkov: roughly 539-750 under the specified availability and return assumptions.
- Jarvis: roughly 405-631 under the specified early-absence and recovery cases.
- Wallstedt: roughly 472-696 with 38/46/56 starts plus two relief appearances.
  Corresponding Gustavsson allocations fall as Wallstedt's rise; reserves receive
  six or eight starts. These are a jointly constrained set of hypothetical plans.

These are conditional scenario totals, not prediction intervals, guaranteed
bounds, expected lineup production or draft targets. Jarvis's assumed 12/24/36
early missed team games and 95% subsequent availability are not a medical
forecast. They need a supported return window and actual schedule mapping.

The goalie report decomposes the change relative to the board into workload at
the old per-appearance rate and the effect of switching to conditional rates.
For Wallstedt's 46-start case, about +216 points comes from workload at the old
rate and +166 from the changed rate basis. Crediting the whole +382 to role would
be misleading. The rate adapter uses the previous regular season's 33 starts
and two relief appearances for Wallstedt, and 49 starts and one relief appearance
for Gustavsson. Relief estimates are especially weak. Provider discrepancies
remain flagged. There is no fitted regression or goalie-quality upgrade here.

Evidence links and short factual notes are stored in the private report. The
Panthers' possible line combinations are editorial possibilities, not confirmed
coach assignments. The Minnesota evidence is newer and more relevant to the
upcoming workload than relying solely on last spring's playoff rotation.

## Reproduce

From the repository root, use new output filenames to preserve earlier results:

```sh
uv run python tools/build_context_pilot.py \
  --board var/prepared-market-2026-09-10/board.json \
  --history var/history-2026.json \
  --goalie-box snapshots/2026-09-10/sportsdataverse/goalie_box_2026.csv \
  --output private/NEW-context-pilot.json
uv run python tools/run_context_scenarios.py \
  --board var/prepared-market-2026-09-10/board.json \
  --input private/NEW-context-pilot.json --as-of 2026-09-10 \
  --output var/NEW-context-pilot.json
```

The builder contains the dated September 10 pilot assumptions. The pure engine
supports sequential skater phases and validated team goalie allocations.
Different evidence/assumptions can be supplied without changing the scoring code.
All inputs are hashed, and neither command opens the live draft SQLite database.

Before promoting a projection: review current evidence, replace speculative
inputs where evidence exists, assess rate shrinkage for small goalie samples,
then compare useful lineup production and injury replacement value. If camp
information is unavailable before the draft, retain multiple cases and expose
that uncertainty in the draft decision instead of inventing a confirmed role.

Validation: 78 tests pass, including phase scoring, goalie start budgets, start/relief separation, future-data rejection and baseline preservation.
