"""Safe, data-driven condition evaluator (no eval). Three-valued: True / False / None (unknown).

Grammar:
  {"all": [cond, ...]} | {"any": [cond, ...]} | {"not": cond}
  {"fact": "dotted.path", "op": OP, "value": X}
  OP in eq, ne, in, not_in, gt, gte, lt, lte, truthy, falsy, exists, contains
Unknown facts (None) make comparisons return None, so the checklist can say "may apply — we need
more information" instead of silently dropping or wrongly applying a requirement.
"""
from __future__ import annotations

from typing import Any

OPS = {"eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "truthy", "falsy", "exists", "contains"}


class ConditionError(ValueError):
    pass


def get_fact(facts: dict, path: str) -> Any:
    cur: Any = facts
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def validate(cond: dict | None) -> None:
    if cond is None:
        return
    if not isinstance(cond, dict):
        raise ConditionError("condition must be an object")
    if "all" in cond or "any" in cond:
        items = cond.get("all", cond.get("any"))
        if not isinstance(items, list) or not items:
            raise ConditionError("all/any need a non-empty list")
        for c in items:
            validate(c)
    elif "not" in cond:
        validate(cond["not"])
    else:
        if not isinstance(cond.get("fact"), str) or cond.get("op") not in OPS:
            raise ConditionError(f"invalid leaf condition: {cond}")


def evaluate(cond: dict | None, facts: dict) -> bool | None:
    if cond is None:
        return True
    if "all" in cond:
        results = [evaluate(c, facts) for c in cond["all"]]
        if any(r is False for r in results):
            return False
        return None if any(r is None for r in results) else True
    if "any" in cond:
        results = [evaluate(c, facts) for c in cond["any"]]
        if any(r is True for r in results):
            return True
        return None if any(r is None for r in results) else False
    if "not" in cond:
        r = evaluate(cond["not"], facts)
        return None if r is None else not r
    value = get_fact(facts, cond["fact"])
    op, target = cond["op"], cond.get("value")
    if op == "exists":
        return value is not None and value != ""
    if op == "truthy":
        return None if value is None else bool(value)
    if op == "falsy":
        return None if value is None else not bool(value)
    if value is None:
        return None
    try:
        if op == "eq":
            return value == target
        if op == "ne":
            return value != target
        if op == "in":
            return value in target
        if op == "not_in":
            return value not in target
        if op == "contains":
            return target in value
        if op == "gt":
            return value > target
        if op == "gte":
            return value >= target
        if op == "lt":
            return value < target
        if op == "lte":
            return value <= target
    except TypeError:
        return None
    raise ConditionError(op)
