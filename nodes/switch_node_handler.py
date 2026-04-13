

from __future__ import annotations
import json
import ast
from typing import Any, Dict

def _evaluate_input(input_expr: Any, context_dict: Dict[str, Any]):
    if isinstance(input_expr, str):
        expr = input_expr.strip()
        if expr.startswith("{{") and expr.endswith("}}"):
            key = expr[2:-2].strip()
            value: Any = context_dict
            for part in key.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value
        return expr
    return input_expr

def _safe_parse_json_maybe(raw: Any):
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(s)
            except Exception:
                return None
    return None

def run(step, context):
    ctx = context.to_dict()
    node_id = step.get("id", "")
    cases: Dict[str, str] = step.get("cases", {})

    input_expr = step.get("input")
    if input_expr is not None:
        print("wata1")
        input_value = _evaluate_input(input_expr, ctx)

    else:
        input_value = None
        if node_id in {"route_behavior_reset", "continue_existing_flow"}:
            input_value = ctx.get("behavior")
        elif node_id == "route_followup_or_reset":
            parsed = _safe_parse_json_maybe(ctx.get("flow_decision"))
            input_value = parsed.get("flow_decision") if isinstance(parsed, dict) else None
        elif node_id == "classify_behavior":
            parsed = _safe_parse_json_maybe(ctx.get("behavior_json"))
            input_value = (parsed or {}).get("behavior") if isinstance(parsed, dict) else ctx.get("behavior_json")
            print("test switch1", input_value)

    if not input_value:
        print("test switch4", input_value)
        parsed = _safe_parse_json_maybe(ctx.get("behavior_json"))
        if isinstance(parsed, dict):
            input_value = parsed.get("behavior")

    if input_value in cases:
        return {}, cases[input_value]
    if "default" in cases:
        return {}, cases["default"]
    raise ValueError(f"[switch_node_handler] No matching case for value: {input_value}")

