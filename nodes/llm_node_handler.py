from __future__ import annotations

import ast
import json
import os
import re
from datetime import date
from typing import Any, Dict
fromt dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

load_dotenv()   



def _clean_json_string(content: str) -> str:
    pattern = r"```(?:json)?\s*(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()


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

def _render_prompt(template_str: str, context) -> str:
    ctx = context.to_dict().copy()

    conversation_history = ctx.get("conversation_history", [])
    if isinstance(conversation_history, list):
        ctx["conversation_history"] = json.dumps(conversation_history, ensure_ascii=False)

    if not template_str:
        return ""

    template = Template(template_str)
    today = date.today()
    parsed = _safe_parse_json_maybe(ctx.get("behavior_json"))
    if isinstance(parsed, dict):
        query_value = parsed.get("final_question")
    else :
        query_value = parsed
    return template.render(
        context=ctx,
        final_question = query_value,
        user_question=ctx.get("user_question", ""),
        current_table=ctx.get("current_table", ""),
        selected_fields=ctx.get("selected_fields", ""),
        tables_list=ctx.get("tables_json", {}),
        current_table_name=ctx.get("behavior_json", {}),
        current_table_fields=ctx.get("fields", []),
        sql_result=ctx.get("sql_result", ""),
        document_vector_result=ctx.get("document_vector_result", []),
        today_date=today.isoformat(),
        tables_to_choose=ctx.get("table_vector_result", []),
        excel_file_list = ctx.get("excel_file_list", []),
        error=ctx.get("error", ""),
        history_chat = ctx.get("history_chat", ""),
    )

def _call_openai_api(prompt: str, model: str):
   

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=os.getenv("OPENAI_BASE_URL"))



    messages: list[ChatCompletionUserMessageParam] = [
        {"role": "user", "content": prompt}
    ]

    print("Model dang su dung de tao answer", model)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        stream=False,
    )

    content = response.choices[0].message.content

    print(content)

    clean_content = _clean_json_string(content)
    try:
        return json.loads(clean_content)
    except json.JSONDecodeError:
        return clean_content


def run(step, context):
    props = step.get("properties", {})

    prompt_template = props.get("prompt", "")
    
    model = "gpt-4o"

    rendered = _render_prompt(prompt_template, context)
    print(f"\n[LLM Node: {step['id']}] Prompt:\n{rendered}\n")

    api_key = context.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    llm_output = _call_openai_api(rendered, model=model)
    print(f"Output từ LM:\n{llm_output}\n")

    if llm_output == "No" and props.get("handle_error"):
        return {}, props["handle_error"]

    output_template = step.get("output", {})
    output_dict: Dict[str, Any] = {}

    history = context.get("conversation_history", [])
    if not isinstance(history, list):
        history = []
    assistant_reply = json.dumps(llm_output, ensure_ascii=False) if isinstance(llm_output, dict) else str(llm_output)
    history.append({"role": "assistant", "content": assistant_reply})
    context.set("conversation_history", history)

    for var_name, template in output_template.items():
        jinja_template = Template(template)
        output_dict[var_name] = jinja_template.render(
            **(llm_output if isinstance(llm_output, dict) else {}),
            llm_output=llm_output,
            context=context.to_dict()
        )
    if props.get("data"):
        context.set(props["data"], output_dict)

    next_step = step.get("next")
    return output_dict, next_step
