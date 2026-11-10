# Market Bot V3

Every call is a falsifiable prediction, stored before the data it predicts
exists, and graded later by rule. Research and education only, not financial advice.

Build status: Component 1 (ledger) done. Morning run, grader, calibration to follow.

## Ledger

    python bot.py ledger add FILE.json [--backfill]
    python bot.py ledger list [--date YYYY-MM-DD]
    python bot.py ledger show ID
    python bot.py ledger verify

- Database: `data/ledger.db` (SQLite, table `predictions`), override with `--db`. Commit and push it after
  every run: the push timestamp is outside proof the prediction predates the outcome.
- Rows are immutable (UPDATE and DELETE abort) and hash chained; `verify` detects edits.
- A prediction is rejected unless it is issued before 09:30 ET on its issue date.
  `--backfill` allows a past date and flags the row BACKFILLED permanently.
- Trigger rules use the grammar in `mbv3/rules.py`. A trigger that cannot be
  written in that grammar is rejected, so it cannot become a Top Play.
- Example input: `examples/nov4_2026_top_plays.json`.

Tests: `python -m unittest discover -s tests`
