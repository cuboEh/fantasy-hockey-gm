# Working guide

Use Python and keep external data access separate from pure scoring calculations.
Do not publish private configuration, source downloads, credentials or league snapshots.
Do not add Yahoo scraping, browser automation or roster writes.
Keep missing data explicit, and distinguish historical statistics from projections.
Run `uv run python -m unittest discover -s tests -v` for scoring changes.
Do not use em dashes in writing.
