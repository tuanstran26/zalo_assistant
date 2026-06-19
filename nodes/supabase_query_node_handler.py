from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")
    return create_client(url, key)


def get_excel_file_names() -> list[str]:
    response = get_supabase_client().table("excel_files").select("file_name").execute()
    return [row["file_name"] for row in response.data or []]


def run(step, context):
    result = get_excel_file_names()
    context.set("excel_file_list", result)
    return {"excel_file_list": result}, step.get("next")
