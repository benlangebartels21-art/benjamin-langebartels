"""Machine-checkable trigger rules.

A trigger is stored as JSON and evaluated against ONE daily bar (open, high,
low, close). If a setup cannot be written in this grammar it cannot be a Top
Play (it may only be listed as Forming).

Trigger document:
{
  "rule": <node>,
  "valid_days": 1,              # trading days from issue date in which the
                                # trigger may fire (<= timeframe)
  "intraday_basis": null        # or "first_30_min" / "opening_range": the
                                # prose depends on intraday data, so daily-bar
                                # grading is labeled APPROXIMATE
}
<node> is {"any": [<node>...]}, {"all": [<node>...]}, or a leaf:
  {"op": "close_above",        "level": x}   close >  x
  {"op": "close_at_or_above",  "level": x}   close >= x
  {"op": "open_above",         "level": x}   open  >  x
  {"op": "high_above",         "level": x}   high  >  x
  {"op": "low_at_or_above",    "level": x}   low   >= x  ("holds x")
  {"op": "low_in_zone", "low": a, "high": b} a <= low <= b ("pulls back to a-b")
"""
from __future__ import annotations

LEVEL_OPS = {
    "close_above": lambda b, x: b["close"] > x,
    "close_at_or_above": lambda b, x: b["close"] >= x,
    "open_above": lambda b, x: b["open"] > x,
    "high_above": lambda b, x: b["high"] > x,
    "low_at_or_above": lambda b, x: b["low"] >= x,
}
INTRADAY_BASES = {
    None: None,
    "first_30_min": "30-minute intraday bars (e.g. Polygon.io or Alpaca minute aggregates)",
    "opening_range": "5-minute intraday bars (e.g. Polygon.io or Alpaca minute aggregates)",
}


class RuleError(ValueError):
    pass


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        raise RuleError(f"{name} must be a positive number, got {v!r}")


def _validate_node(node):
    if not isinstance(node, dict):
        raise RuleError(f"rule node must be an object, got {node!r}")
    for comb in ("any", "all"):
        if comb in node:
            if set(node) != {comb} or not isinstance(node[comb], list) or not node[comb]:
                raise RuleError(f"'{comb}' must be the only key and hold a non-empty list")
            for child in node[comb]:
                _validate_node(child)
            return
    op = node.get("op")
    if op in LEVEL_OPS:
        if set(node) != {"op", "level"}:
            raise RuleError(f"{op} takes exactly 'level'")
        _num(node["level"], "level")
    elif op == "low_in_zone":
        if set(node) != {"op", "low", "high"}:
            raise RuleError("low_in_zone takes exactly 'low' and 'high'")
        _num(node["low"], "low")
        _num(node["high"], "high")
        if node["low"] > node["high"]:
            raise RuleError("low_in_zone: low must be <= high")
    else:
        raise RuleError(f"unknown op {op!r}; trigger is not machine-checkable")


def validate_trigger(trigger, timeframe_days):
    """Raise RuleError unless `trigger` is a gradable trigger document."""
    if not isinstance(trigger, dict) or set(trigger) != {"rule", "valid_days", "intraday_basis"}:
        raise RuleError("trigger needs exactly: rule, valid_days, intraday_basis")
    vd = trigger["valid_days"]
    if isinstance(vd, bool) or not isinstance(vd, int) or not 1 <= vd <= timeframe_days:
        raise RuleError(f"valid_days must be an integer from 1 to timeframe ({timeframe_days})")
    if trigger["intraday_basis"] not in INTRADAY_BASES:
        raise RuleError(f"intraday_basis must be one of {sorted(k for k in INTRADAY_BASES if k)} or null")
    _validate_node(trigger["rule"])


def is_approximate(trigger):
    return trigger["intraday_basis"] is not None


def exact_data_source(trigger):
    return INTRADAY_BASES[trigger["intraday_basis"]]


def evaluate(node, bar):
    """True if the rule node is satisfied by one daily bar dict (open/high/low/close)."""
    if "any" in node:
        return any(evaluate(c, bar) for c in node["any"])
    if "all" in node:
        return all(evaluate(c, bar) for c in node["all"])
    if node["op"] == "low_in_zone":
        return node["low"] <= bar["low"] <= node["high"]
    return LEVEL_OPS[node["op"]](bar, node["level"])
