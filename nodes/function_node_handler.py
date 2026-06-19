from __future__ import annotations

import logging
import os
import re
import uuid
from collections.abc import Callable
from typing import Any

from jinja2 import Template

from nodes.utils import parse_json_maybe, render_template


logger = logging.getLogger(__name__)


def parse_json_fields(data: Any, fields: list[str]) -> dict[str, Any]:
    parsed = parse_json_maybe(data) if isinstance(data, str) else data
    if not isinstance(parsed, dict):
        raise ValueError("Input must be a JSON object.")
    return {field: parsed.get(field, "") for field in fields}


def validate_select_query(query: str) -> str:
    pattern = r"^\s*SELECT\s+.+\s+FROM\s+.+"
    if not query or not re.match(pattern, query, re.IGNORECASE):
        raise ValueError("Invalid SQL: only SELECT queries are allowed.")
    return query.strip()


def create_file_and_get_link(data: str | None) -> str:
    if data is None:
        raise ValueError("Missing 'data' for file creation.")

    filename = f"data_{uuid.uuid4().hex}.txt"
    filepath = os.path.join("downloads", filename)
    os.makedirs("downloads", exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data)

    return f"/downloads/{filename}"


def _run_function(function_name: str, rendered_input: dict[str, Any]) -> Any:
    functions: dict[str, Callable[[dict[str, Any]], Any]] = {
        "parse_json_fields": lambda data: parse_json_fields(
            data.get("json_string"),
            data.get("fields", []),
        ),
        "validate_select_query": lambda data: validate_select_query(data.get("query", "")),
        "create_file_and_get_link": lambda data: create_file_and_get_link(data.get("data")),
    }

    try:
        return functions[function_name](rendered_input)
    except KeyError as exc:
        raise ValueError(f"Function '{function_name}' is not supported.") from exc


def run(step, context):
    context_dict = context.to_dict()
    rendered_input = render_template(step.get("input", {}), context_dict)
    if not isinstance(rendered_input, dict):
        raise ValueError("Function node input must render to an object.")

    function_name = step.get("function")
    if not function_name:
        raise ValueError("Function node is missing a function name.")

    logger.debug("Running function node %s with input %s", function_name, rendered_input)
    result = _run_function(function_name, rendered_input)

    output_dict: dict[str, Any] = {}
    for key, template in step.get("output", {}).items():
        try:
            output_dict[key] = Template(template).render(result=result, context=context_dict)
        except Exception:
            logger.exception("Error rendering function output '%s'", key)
            output_dict[key] = ""

    return output_dict, step.get("next")
