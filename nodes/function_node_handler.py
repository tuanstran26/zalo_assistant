import json
import re
import os
import uuid
from jinja2 import Template
import ast

def render_template(value, context_dict):
    if isinstance(value, str):
        return Template(value).render(**context_dict)
    elif isinstance(value, list):
        return [render_template(v, context_dict) for v in value]
    elif isinstance(value, dict):
        return {k: render_template(v, context_dict) for k, v in value.items()}
    return value



def parse_json_fields(data_dict, fields):
    print(f"📥 Input JSON dict: {data_dict}")
    if not isinstance(data_dict, dict):
        raise ValueError("Input must be a JSON dict.")
    result = {field: data_dict.get(field, "") for field in fields}
    print(f"✅ Parsed fields: {result}")
    return result


def validate_select_query(query):
    pattern = r"^\s*SELECT\s+.+\s+FROM\s+.+" 
    if re.match(pattern, query, re.IGNORECASE):
        return query.strip()
    else:
        raise ValueError("Invalid SQL: Only SELECT queries are allowed.")

def create_file_and_get_link(data):
    try:
        filename = f"data_{uuid.uuid4().hex}.txt"
        filepath = os.path.join("downloads", filename)
        os.makedirs("downloads", exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(data)

        return f"/downloads/{filename}"  
    except Exception as e:
        print(f"Error creating file: {e}")
        return None


def run(step, context):
    context_dict = context.to_dict()
    input_template = step.get("input", {})
    rendered_input = render_template(input_template, context_dict)

    function_name = step.get("function")
    output_mapping = step.get("output", {})
    next_step = step.get("next")

    print(f"Running function node: {function_name}")
    print(f"Input after rendering: {rendered_input}")

    if function_name == "parse_json_fields":
        json_data = rendered_input["json_string"]

        print(json_data)
        if isinstance(json_data, str):
            try:
                json_data = ast.literal_eval(json_data)
            except Exception as e:
                raise ValueError(f"Không thể chuyển chuỗi thành dict: {e}")

        fields = rendered_input.get("fields", [])
        result = parse_json_fields(json_data, fields)

    elif function_name == "validate_select_query":
        query = rendered_input.get("query")
        if not query:
            raise ValueError("Missing SQL query for validation.")
        result = validate_select_query(query)

    elif function_name == "create_file_and_get_link":
        data = rendered_input.get("data")
        if data is None:
            raise ValueError("Missing 'data' for file creation.")
        result = create_file_and_get_link(data)

    else:
        raise ValueError(f"Function '{function_name}' is not supported.")

    output_dict = {}
    for key, template in output_mapping.items():
        try:
            jinja_template = Template(template)
            output_value = jinja_template.render(result=result, context=context_dict)
            output_dict[key] = output_value
        except Exception as e:
            print(f"⚠️ Error rendering output '{key}': {e}")
            output_dict[key] = ""

    print(f"Output to context: {output_dict}")
    return output_dict, next_step