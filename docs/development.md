# Draft preparation development

The local foundation includes an offline scoring calculator and a skater role
scenario projector. They convert explicit inputs into fantasy points with
contribution breakdowns and input hashes. They do not estimate rates from real
player data, rank real players, optimize lineups, enforce transaction rules, or
track a draft yet.

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

1. Select a permitted projection source and verify all scored fields, season,
   units, identities, and Yahoo position eligibility. Preserve provenance.
2. Score normalized projections with coverage flags and export a ranked table.
3. Add position-specific replacement estimates and configurable league size.
4. Add manual draft tracking, persistent state, pick correction and candidate
   explanations. Keep provider IDs distinct from internal player IDs.
5. Rehearse a draft and export a static fallback before the actual draft.

Use SQLite when draft state and player records are introduced. No database is
needed to score an isolated stat line. Future weekly analysis should value usable
lineup opportunities; total season projections alone are not a draft strategy.
