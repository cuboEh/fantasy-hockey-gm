# Working guide

Use Python and keep external data access separate from pure scoring calculations.
Do not publish private configuration, source downloads, credentials or league snapshots.
Do not add Yahoo scraping, Yahoo browser automation or roster writes.
Local dashboard browser verification in isolated practice sessions is authorized
by the user (September 12, 2026). Keep the live draft session untouched.
Keep missing data explicit, and distinguish historical statistics from projections.
Run `uv run python -m unittest discover -s tests -v` for scoring changes.
Do not use em dashes in writing.

## PRD workflow

The active delivery contract is [PRD 2.0](docs/PRD-2.0.md).
Read it and [the development workflow](docs/reference/prd-workflow.md) before feature work.
`docs/product-plan.md` retains product context and future ideas; the active PRD
governs the current increment. User instructions take precedence.
Use [the documentation index](docs/README.md) to find guides, references and
archived evidence. Preserve this layout and update links when moving documents.

- Identify the phase and FR IDs addressed before implementation.
- Reuse existing code and evidence. Verify existing behavior before rebuilding it.
- Define an observable acceptance check before changing code or running experiments.
- Keep statistics primary. Never tune toward preferred player names or force a
  recommendation to differ from the points-first baseline.
- Mark an FR Done only with verification evidence in its Notes column.
- Run required checks once per relevant change; repeat for failures, new changes,
  or unresolved concerns. Every broader experiment needs a decision and stopping rule.
- Record unrelated discoveries as future work without expanding the active release.
- Preserve private inputs and live draft state. Rehearse in isolated sessions.
- Commit verified development milestones and push the development branch to origin
  so progress is logged and earlier builds remain recoverable (user request,
  September 14, 2026). Review staged files for private data before committing.
  Preserve previous release branches; do not force-push or rewrite checkpoints.
