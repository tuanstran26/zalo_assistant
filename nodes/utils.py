from __future__ import annotations

import ast
import json
import re
from typing import Any, Mapping

from jinja2 import Template


FENCED_JSON_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def clean_fenced_content(content: str) -> str:
    match = FENCED_JSON_PATTERN.search(content)
    return match.group(1).strip() if match else content.strip()


def parse_json_maybe(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        value = clean_fenced_content(raw)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return None
    return None


def render_template(value: Any, context: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return Template(value).render(**context)
    if isinstance(value, list):
        return [render_template(item, context) for item in value]
    if isinstance(value, dict):
        return {key: render_template(item, context) for key, item in value.items()}
    return value


def resolve_context_expression(expression: Any, context: Mapping[str, Any]) -> Any:
    if not isinstance(expression, str):
        return expression

    value = expression.strip()
    if not (value.startswith("{{") and value.endswith("}}")):
        return value

    path = value[2:-2].strip()
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def final_question_from_behavior(context: Mapping[str, Any]) -> Any:
    parsed = parse_json_maybe(context.get("behavior_json"))
    if isinstance(parsed, Mapping):
        return parsed.get("final_question")
    return parsed
