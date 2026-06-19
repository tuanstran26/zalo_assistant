from __future__ import annotations

from typing import Any

from nodes.utils import parse_json_maybe, resolve_context_expression


def _fallback_input_value(node_id: str, context: dict[str, Any]) -> Any:
    if node_id in {"route_behavior_reset", "continue_existing_flow"}:
        return context.get("behavior")

    if node_id == "route_followup_or_reset":
        parsed = parse_json_maybe(context.get("flow_decision"))
        return parsed.get("flow_decision") if isinstance(parsed, dict) else None

    if node_id == "classify_behavior":
        parsed = parse_json_maybe(context.get("behavior_json"))
        return parsed.get("behavior") if isinstance(parsed, dict) else context.get("behavior_json")

    parsed = parse_json_maybe(context.get("behavior_json"))
    return parsed.get("behavior") if isinstance(parsed, dict) else None


def run(step, context):
    ctx = context.to_dict()
    cases: dict[str, str] = step.get("cases", {})

    input_expr = step.get("input")
    input_value = (
        resolve_context_expression(input_expr, ctx)
        if input_expr is not None
        else _fallback_input_value(step.get("id", ""), ctx)
    )

    if not input_value:
        input_value = _fallback_input_value(step.get("id", ""), ctx)

    if input_value in cases:
        return {}, cases[input_value]
    if "default" in cases:
        return {}, cases["default"]

    raise ValueError(f"[switch_node_handler] No matching case for value: {input_value}")
