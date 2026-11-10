import copy
import json
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mbv3 import ledger, rules  # noqa: E402

PRE_OPEN = datetime(2026, 11, 4, 13, 0, tzinfo=timezone.utc)   # 08:00 ET
POST_OPEN = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)  # 10:00 ET
ANET, AMD = json.loads((ROOT / "examples" / "nov4_2026_top_plays.json").read_text())


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.conn = ledger.connect(":memory:")

    def add(self, p=ANET, **kw):
        kw.setdefault("now", PRE_OPEN)
        return ledger.add_prediction(self.conn, copy.deepcopy(p), **kw)

    def bad(self, **changes):
        p = copy.deepcopy(ANET)
        p.update(changes)
        with self.assertRaises(ledger.LedgerError):
            self.add(p)

    def test_roundtrip(self):
        pid = self.add()
        row = ledger.get_prediction(self.conn, pid)
        self.assertEqual(row["ticker"], "ANET")
        self.assertEqual(row["trigger_rule"], ANET["trigger_rule"])
        self.assertEqual(row["trigger_prose"], ANET["trigger_prose"])
        self.assertEqual(row["backfilled"], 0)
        self.assertEqual(row["issued_at_utc"], "2026-11-04T13:00:00+00:00")

    def test_must_be_issued_before_open(self):
        with self.assertRaises(ledger.LedgerError):
            self.add(now=POST_OPEN)
        pid = self.add(now=POST_OPEN, backfill=True)
        self.assertEqual(ledger.get_prediction(self.conn, pid)["backfilled"], 1)

    def test_rejects_ungradable(self):
        self.bad(trigger_rule=None)
        self.bad(trigger_rule={"rule": {"op": "looks_strong"}, "valid_days": 1, "intraday_basis": None})
        self.bad(trigger_rule={"rule": {"op": "close_above", "level": 186}, "valid_days": 16, "intraday_basis": None})
        self.bad(trigger_prose="")
        self.bad(direction="short")
        self.bad(score=11)
        self.bad(confidence_pct=100)
        self.bad(stop_price=200)          # stop above target1
        self.bad(stop_type="mental")
        self.bad(strategy="vibes")
        self.bad(timeframe_days=0)

    def test_immutable(self):
        pid = self.add()
        for sql in ("UPDATE predictions SET target1 = 1 WHERE id = ?", "DELETE FROM predictions WHERE id = ?"):
            with self.assertRaises(sqlite3.DatabaseError):
                self.conn.execute(sql, (pid,))

    def test_chain_detects_tampering(self):
        self.add()
        self.add(AMD)
        self.assertTrue(ledger.verify_chain(self.conn)[0])
        self.conn.execute("DROP TRIGGER predictions_no_update")
        self.conn.execute("UPDATE predictions SET confidence_pct = 99 WHERE id = 1")
        ok, msg = ledger.verify_chain(self.conn)
        self.assertFalse(ok)
        self.assertIn("prediction 1", msg)


class RuleTest(unittest.TestCase):
    def test_nov4_bars_do_not_fire(self):
        # Close and high are the actuals supplied for 2026-11-04. Open and low were
        # not supplied; the values used are the most favorable to the trigger that
        # are consistent with the known close, so a pass here would be a real bug.
        anet = {"open": 186.5, "high": 188.53, "low": 178.48, "close": 178.48}
        amd = {"open": 510.0, "high": 514.61, "low": 476.50, "close": 488.78}
        self.assertFalse(rules.evaluate(ANET["trigger_rule"]["rule"], anet))
        self.assertFalse(rules.evaluate(AMD["trigger_rule"]["rule"], amd))
        self.assertTrue(rules.is_approximate(ANET["trigger_rule"]))

    def test_ops(self):
        bar = {"open": 187, "high": 190, "low": 183, "close": 189}
        self.assertTrue(rules.evaluate(ANET["trigger_rule"]["rule"], bar))
        self.assertTrue(rules.evaluate({"op": "low_in_zone", "low": 182, "high": 186}, bar))
        self.assertFalse(rules.evaluate({"op": "high_above", "level": 190}, bar))


if __name__ == "__main__":
    unittest.main()
