import os
import numpy as np
from typing import Any
import json
import ast
from supabase import create_client
from langchain_huggingface import HuggingFaceEmbeddings

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "vector_store_table"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EMBED_MODEL_NAME = "BAAI/bge-m3"
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cpu")

embed_model = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL_NAME,
    model_kwargs={"device": EMBED_DEVICE}
)


def retrieve_similar_docs(query_text: str, top_k: int = 40, min_score: float = 0.3):
 
    query_embedding = embed_model.embed_query(query_text)
    query_embedding = np.array(query_embedding).tolist()

    response = supabase.rpc("match_vectors", {
        "query_embedding": query_embedding,
        "match_count": top_k * 2  #
    }).execute()

    if not response.data:
        print(" Không tìm thấy tài liệu nào trong cơ sở dữ liệu.")
        return []

    filtered_results = [
        {
       
            "content": item["content"],
        }
        for item in response.data
        if item["similarity"] >= min_score
    ][:top_k]

    return filtered_results

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
    parsed = _safe_parse_json_maybe(ctx.get("behavior_json"))
    if isinstance(parsed, dict):
        query_value = parsed.get("final_question")
    else:
        query_value = parsed
    print("query value",query_value)
    if query_value is None:
        return {"vector_result": "cant find"}, step.get("next")
    else:
        result = retrieve_similar_docs(query_value)
        context.set("document_vector_result", result)
        return {"document_vector_result": result}, step.get("next")


if __name__ == "__main__":
    query = "Khung cảnh thiên nhiên nơi này yên bình, thanh tịnh đến lạ kỳ"
    print(f"\n🔍 Truy vấn: {query}\n")

    results = retrieve_similar_docs(query, top_k=40, min_score=0.3)

    if not results:
        print(" Không tìm thấy chunk nào đạt ngưỡng similarity yêu cầu.")
    else:
        print(f"Tổng số chunk lấy được: {len(results)}\n")
        for i, doc in enumerate(results, 1):
            preview = doc['content'][:300].replace("\n", " ")
            print(f"Nội dung: {preview}...")
            print("----------------------------------------\n")
