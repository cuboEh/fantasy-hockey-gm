# Draft preparation development

The first local slice is an offline scoring calculator. It converts a normalized
stat line into fantasy points with a contribution breakdown and input hashes.
It does not produce projections, rank real players, optimize lineups, enforce
transaction rules, or track a draft yet.

## Run

Python 3.11 or newer and uv:

```sh
uv sync --locked
uv run fantasy score --config config.example.toml --input examples/skater.json
uv run fantasy score --config config.example.toml --input examples/goalie.json
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
to a later validated projection adapter. Decimal output is serialized as strings.

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
