from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import numpy as np
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from supabase import Client, create_client


load_dotenv()

EMBED_MODEL_NAME = "BAAI/bge-m3"
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cpu")


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")
    return create_client(url, key)


@lru_cache(maxsize=1)
def get_embed_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL_NAME,
        model_kwargs={"device": EMBED_DEVICE},
    )


def retrieve_excel_docs(
    query_text: str,
    top_k: int = 1,
    min_score: float = 0.3,
) -> list[dict[str, Any]]:
    query_embedding = np.array(get_embed_model().embed_query(query_text)).tolist()
    response = get_supabase_client().rpc(
        "match_excel_vectors",
        {
            "query_embedding": query_embedding,
            "match_count": top_k * 2,
        },
    ).execute()

    if not response.data:
        return []

    return [
        {
            "file_name": item["file_name"],
            "similarity": round(item["similarity"], 4),
            "content": item["content"],
            "metadata": item["metadata"],
        }
        for item in response.data
        if item["similarity"] >= min_score
    ][:top_k]


def run(step, context):
    parsed = context.get("excel_file_name")
    query_value = parsed.get("excel_file_name") if isinstance(parsed, dict) else parsed
    if not query_value:
        return {"document_vector_result": []}, step.get("next")

    props = step.get("properties", {})
    result = retrieve_excel_docs(
        str(query_value),
        top_k=int(props.get("top_k", 1)),
        min_score=float(props.get("min_score", 0.3)),
    )
    output_name = props.get("result_name", "document_vector_result")
    context.set(output_name, result)
    return {output_name: result}, step.get("next")
