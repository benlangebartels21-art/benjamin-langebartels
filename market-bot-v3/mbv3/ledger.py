"""Prediction ledger: append-only SQLite store of falsifiable predictions.

Guarantees
- One row per prediction, validated to be machine-gradable before it is written.
- Rows are immutable: SQLite triggers abort any UPDATE or DELETE.
- A prediction must be issued before the 09:30 ET open of its issue date, so it
  is always written before the data it predicts exists. The only exception is
  an explicit backfill, which is permanently flagged (backfilled = 1).
- Rows are hash-chained (row_hash covers the content plus the previous hash),
  so edits made outside this code are detectable with verify_chain().
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import rules

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "ledger.db"

TYPES = ("swing", "day")
STRATEGIES = (
    "post_earnings_drift",
    "breakout",
    "pullback_to_support",
    "news_continuation",
    "oversold_reversal",
    "insider_follow",
)
STOP_TYPES = ("close", "touch")  # close-based or price-touch
ENTRY_RULES = ("close_on_trigger_day",)  # entry = close of the bar where the trigger fires

# Column order is also the hash order. Do not reorder.
FIELDS = (
    "issued_at_utc", "issue_date", "ticker", "type", "strategy", "direction",
    "score", "confidence_pct", "trigger_rule", "trigger_prose", "entry_rule",
    "stop_price", "stop_type", "target1", "target2", "timeframe_days",
    "catalyst", "scoring_version", "backfilled",
)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    issued_at_utc   TEXT NOT NULL,
    issue_date      TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN {TYPES}),
    strategy        TEXT NOT NULL CHECK (strategy IN {STRATEGIES}),
    direction       TEXT NOT NULL CHECK (direction = 'long'),
    score           REAL NOT NULL CHECK (score BETWEEN 0 AND 10),
    confidence_pct  REAL NOT NULL CHECK (confidence_pct > 0 AND confidence_pct < 100),
    trigger_rule    TEXT NOT NULL,
    trigger_prose   TEXT NOT NULL,
    entry_rule      TEXT NOT NULL,
    stop_price      REAL NOT NULL CHECK (stop_price > 0),
    stop_type       TEXT NOT NULL CHECK (stop_type IN {STOP_TYPES}),
    target1         REAL NOT NULL,
    target2         REAL NOT NULL,
    timeframe_days  INTEGER NOT NULL CHECK (timeframe_days >= 1),
    catalyst        TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    backfilled      INTEGER NOT NULL CHECK (backfilled IN (0, 1)),
    prev_hash       TEXT NOT NULL,
    row_hash        TEXT NOT NULL UNIQUE,
    CHECK (stop_price < target1 AND target1 <= target2)
);
CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions
BEGIN SELECT RAISE(ABORT, 'predictions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions
BEGIN SELECT RAISE(ABORT, 'predictions are immutable'); END;
"""

GENESIS = "0" * 64


class LedgerError(ValueError):
    pass


def connect(db_path=DEFAULT_DB):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _hash(prev_hash, values):
    payload = json.dumps([prev_hash, *values], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _require(cond, msg):
    if not cond:
        raise LedgerError(msg)


def _number(p, key):
    v = p.get(key)
    _require(isinstance(v, (int, float)) and not isinstance(v, bool), f"{key} must be a number")
    return float(v)


def add_prediction(conn, p, *, now=None, backfill=False):
    """Validate and append one prediction. Returns the new prediction id.

    `p` keys: ticker, type, strategy, score, confidence_pct, trigger_rule (dict),
    trigger_prose, stop_price, stop_type, target1, target2, timeframe_days,
    catalyst, scoring_version; optional issue_date (default: today ET),
    direction (default long), entry_rule (default close_on_trigger_day).
    """
    now = now or datetime.now(timezone.utc)
    _require(now.tzinfo is not None, "now must be timezone-aware")
    now_et = now.astimezone(ET)
    issue_date = date.fromisoformat(p.get("issue_date") or now_et.date().isoformat())

    if not backfill:
        cutoff = datetime.combine(issue_date, MARKET_OPEN, ET)
        _require(
            now_et < cutoff,
            f"issue_date {issue_date} opens at 09:30 ET and it is already "
            f"{now_et:%Y-%m-%d %H:%M} ET. A prediction must be written before the "
            "data it predicts exists; issue it for the next trading day.",
        )

    ticker = str(p.get("ticker", "")).strip().upper()
    _require(ticker and ticker.replace(".", "").replace("-", "").isalnum(), "ticker is required")
    _require(p.get("type") in TYPES, f"type must be one of {TYPES}")
    _require(p.get("strategy") in STRATEGIES, f"strategy must be one of {STRATEGIES}")
    _require(p.get("direction", "long") == "long", "v1 is long only")
    score = _number(p, "score")
    _require(0 <= score <= 10, "score must be 0 to 10")
    conf = _number(p, "confidence_pct")
    _require(0 < conf < 100, "confidence_pct must be between 0 and 100 (exclusive)")
    stop, t1, t2 = _number(p, "stop_price"), _number(p, "target1"), _number(p, "target2")
    _require(0 < stop < t1 <= t2, "need 0 < stop_price < target1 <= target2 (long only)")
    _require(p.get("stop_type") in STOP_TYPES, f"stop_type must be one of {STOP_TYPES}")
    tf = p.get("timeframe_days")
    _require(isinstance(tf, int) and not isinstance(tf, bool) and tf >= 1, "timeframe_days must be an integer >= 1")
    entry_rule = p.get("entry_rule", ENTRY_RULES[0])
    _require(entry_rule in ENTRY_RULES, f"entry_rule must be one of {ENTRY_RULES}")
    for key in ("trigger_prose", "catalyst", "scoring_version"):
        _require(isinstance(p.get(key), str) and p[key].strip(), f"{key} is required")
    try:
        rules.validate_trigger(p.get("trigger_rule"), tf)
    except rules.RuleError as e:
        raise LedgerError(f"trigger_rule is not machine-checkable: {e}") from e

    values = (
        now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        issue_date.isoformat(), ticker, p["type"], p["strategy"], "long",
        score, conf,
        json.dumps(p["trigger_rule"], sort_keys=True, separators=(",", ":")),
        p["trigger_prose"].strip(), entry_rule, stop, p["stop_type"], t1, t2, tf,
        p["catalyst"].strip(), p["scoring_version"].strip(), int(backfill),
    )
    with conn:  # one transaction: read chain tip, then append
        conn.execute("BEGIN IMMEDIATE")
        tip = conn.execute("SELECT row_hash FROM predictions ORDER BY id DESC LIMIT 1").fetchone()
        prev = tip["row_hash"] if tip else GENESIS
        cur = conn.execute(
            f"INSERT INTO predictions ({', '.join(FIELDS)}, prev_hash, row_hash) "
            f"VALUES ({', '.join('?' * (len(FIELDS) + 2))})",
            (*values, prev, _hash(prev, values)),
        )
    return cur.lastrowid


def get_prediction(conn, pid):
    row = conn.execute("SELECT * FROM predictions WHERE id = ?", (pid,)).fetchone()
    if row is None:
        raise LedgerError(f"no prediction with id {pid}")
    d = dict(row)
    d["trigger_rule"] = json.loads(d["trigger_rule"])
    return d


def list_predictions(conn, issue_date=None):
    q, args = "SELECT id FROM predictions", ()
    if issue_date:
        q, args = q + " WHERE issue_date = ?", (issue_date,)
    return [get_prediction(conn, r["id"]) for r in conn.execute(q + " ORDER BY id", args)]


def verify_chain(conn):
    """Recompute every hash. Returns (ok, message)."""
    prev, n = GENESIS, 0
    for row in conn.execute("SELECT * FROM predictions ORDER BY id"):
        values = tuple(row[f] for f in FIELDS)
        if row["prev_hash"] != prev or row["row_hash"] != _hash(prev, values):
            return False, f"chain broken at prediction {row['id']}"
        prev, n = row["row_hash"], n + 1
    return True, f"{n} predictions, chain intact"
