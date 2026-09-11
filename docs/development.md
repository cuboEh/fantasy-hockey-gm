# Draft preparation development

The local implementation includes offline scoring, explicit skater role scenarios,
a historical-rate player board, CSV export and persistent manual draft tracking.
See [draft-day instructions](draft-day.md) for real-player commands and limitations.
The historical pipeline now includes daily opportunity selection and streaming
research. See [six-step implementation](six-step-implementation.md). There is no
validated fitted forecast or automated Yahoo integration.

## Run

Python 3.11 or newer and uv:

```sh
uv sync --locked
uv run fantasy score --config config.example.toml --input examples/skater.json
uv run fantasy score --config config.example.toml --input examples/goalie.json
uv run fantasy project-roles --config config.example.toml --input examples/roles.json
uv run python -m unittest discover -s tests -v
```

The example configuration and stat lines are fictional. Personal league settings
belong in ignored `config.local.toml`. Substitute that path to use local weights.
Missing nonzero-weighted stats fail rather than being interpreted as zero.
Counting statistics must be finite and nonnegative; plus/minus can be negative.
Fractional projected amounts are accepted and decimal arithmetic is used.

Each input declares `basis` (`total` or `per_game`), `data_type` (`historical`,
`projection`, or `illustrative`), `source`, `horizon`, `kind`, and `stats`.
All statistics in one input must share its declared basis and horizon. The scorer
does not infer per-game rates or multiply by appearances. That conversion belongs
to the separate role projector or a future projection adapter. Decimal output is
serialized as strings.

## Role scenarios

`project-roles` accepts mutually exclusive skater roles for one player and horizon.
Each role supplies appearances, PP/non-PP minutes per appearance, and production
rates per 60 minutes for each situation. PP must include every power-play strength;
non-PP includes everything else. Do not supply all-situation rates as non-PP rates.

Goals and assists from the two situations combine into their normal scoring
totals. PP goals plus PP assists also produce the configured PPP bonus. PPP cannot
be supplied separately, preventing inconsistent double adjustments. Negative
plus/minus rates are allowed. Missing scored rates for nonzero exposure fail;
unscored stats are omitted from output rather than labeled as projected zeros.

Probabilities must sum to one and are explicitly labeled supplied assumptions,
not calibrated estimates. Output reports each scenario, probability-weighted
production and points, sources, rationales, and review warnings. Evidence dated
after `as_of` is rejected. The min/max of positive-probability scenario means is
not a prediction interval; random game outcomes are not simulated.

The example is fictional. Scenarios need a common horizon, matching units and
rates conditional on their role. Correlations between exposure and performance
must be represented through scenarios; this version does not learn them. Source
and date fields document claims but do not independently verify them. Goalie
workload scenarios and direct PP-share-to-minutes estimation remain future work.

Public code uses a generic example configuration. Private settings and downloaded
data remain ignored; neither should be added to Git. Yahoo credentials are not
needed for this slice.

## Next slices

1. Verify Yahoo eligibility and current workload/role assumptions; review source conflicts.
2. Add separately sourced rookie projections and compare a permitted independent export.
3. Add position-specific replacement estimates, keeping league size configurable.
4. Evaluate strategies with historical information cutoffs, avoiding future leakage.
5. Confirm final team count and slot, then rehearse the reviewed board and export a fallback.

SQLite stores the frozen board, picks and correction audit. The baseline currently
ranks season points among players who fit available roster slots. Replacement
value, ADP and next-pick availability are not implemented. Future weekly analysis
must value usable lineup opportunities, not simply season totals.
