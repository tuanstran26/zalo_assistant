from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any, Mapping

from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

from nodes.utils import clean_fenced_content, parse_json_maybe


load_dotenv()
logger = logging.getLogger(__name__)


class OpenAIChatClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

    def complete(self, prompt: str, model: str) -> Any:
        messages: list[ChatCompletionUserMessageParam] = [
            {"role": "user", "content": prompt}
        ]
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        cleaned = clean_fenced_content(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return cleaned


def _render_prompt(template_str: str, context) -> str:
    ctx = context.to_dict()
    conversation_history = ctx.get("conversation_history", [])
    if isinstance(conversation_history, list):
        ctx["conversation_history"] = json.dumps(
            conversation_history,
            ensure_ascii=False,
        )

    if not template_str:
        return ""

    parsed_behavior = parse_json_maybe(ctx.get("behavior_json"))
    final_question = (
        parsed_behavior.get("final_question")
        if isinstance(parsed_behavior, Mapping)
        else parsed_behavior
    )

    return Template(template_str).render(
        context=ctx,
        final_question=final_question,
        user_question=ctx.get("user_question", ""),
        current_table=ctx.get("current_table", ""),
        selected_fields=ctx.get("selected_fields", ""),
        tables_list=ctx.get("tables_json", {}),
        current_table_name=ctx.get("behavior_json", {}),
        current_table_fields=ctx.get("fields", []),
        sql_result=ctx.get("sql_result", ""),
        document_vector_result=ctx.get("document_vector_result", []),
        today_date=date.today().isoformat(),
        tables_to_choose=ctx.get("table_vector_result", []),
        excel_file_list=ctx.get("excel_file_list", []),
        error=ctx.get("error", ""),
        history_chat=ctx.get("history_chat", ""),
    )


def _append_assistant_message(context, llm_output: Any) -> None:
    history = context.get("conversation_history", [])
    if not isinstance(history, list):
        history = []
    assistant_reply = (
        json.dumps(llm_output, ensure_ascii=False)
        if isinstance(llm_output, dict)
        else str(llm_output)
    )
    history.append({"role": "assistant", "content": assistant_reply})
    context.set("conversation_history", history)


def run(step, context):
    props = step.get("properties", {})
    prompt_template = props.get("prompt", "")
    model = props.get("model", "gpt-4o")

    rendered_prompt = _render_prompt(prompt_template, context)
    logger.debug("LLM node %s prompt: %s", step.get("id"), rendered_prompt)

    client = OpenAIChatClient(api_key=context.get("openai_api_key"))
    llm_output = client.complete(rendered_prompt, model=model)
    logger.debug("LLM node %s output: %s", step.get("id"), llm_output)

    if llm_output == "No" and props.get("handle_error"):
        return {}, props["handle_error"]

    _append_assistant_message(context, llm_output)

    output_dict: dict[str, Any] = {}
    for var_name, template in step.get("output", {}).items():
        output_dict[var_name] = Template(template).render(
            **(llm_output if isinstance(llm_output, dict) else {}),
            llm_output=llm_output,
            context=context.to_dict(),
        )

    if props.get("data"):
        context.set(props["data"], output_dict)

    return output_dict, step.get("next")
