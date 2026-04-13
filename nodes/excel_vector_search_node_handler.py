import os
from dotenv import load_dotenv
import numpy as np
import json
import ast
from typing import Any
from supabase import create_client
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Embedding model (BGE M3)
EMBED_MODEL_NAME = "BAAI/bge-m3"
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cpu")

embed_model = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL_NAME,
    model_kwargs={"device": EMBED_DEVICE}
)

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


def retrieve_excel_docs(query_text: str, top_k: int = 1, min_score: float = 0.3):
    """
    Tạo embedding cho câu truy vấn và tìm Excel file content tương tự.
    """
    query_embedding = embed_model.embed_query(query_text)
    query_embedding = np.array(query_embedding).tolist()

    response = supabase.rpc("match_excel_vectors", {
        "query_embedding": query_embedding,
        "match_count": top_k * 2
    }).execute()

    if not response.data:
        print("⚠️ Không tìm thấy dữ liệu Excel phù hợp.")
        return []

    filtered = [
        {
            "file_name": item["file_name"],
            "similarity": round(item["similarity"], 4),
            "content": item["content"],
            "metadata": item["metadata"],
        }
        for item in response.data
        if item["similarity"] >= min_score
    ][:top_k]

    return filtered



def run(step, context):
    ctx = context.to_dict()
    parsed = ctx.get("excel_file_name")
    if isinstance(parsed, dict):
        query_value = parsed.get("excel_file_name")
    else:
        query_value = str(parsed)
    print("query value",parsed)
    if query_value is None:
        return {"vector_result": "cant find"}, step.get("next")
    else:
        result = retrieve_excel_docs(query_value)
        context.set("document_vector_result", result)
        return {"document_vector_result": result}, step.get("next")

if __name__ == "__main__":
    query = "group2.xlsx"
    print(f"\n🔍 Truy vấn Excel: {query}\n")

    results = retrieve_excel_docs(query, top_k=10, min_score=0.3)

    if not results:
        print("❌ Không tìm thấy dữ liệu nào tương đồng.")
    else:
        print(f"✅ Tìm thấy {len(results)} kết quả tương tự:\n")
        for i, item in enumerate(results, 1):
            print(f"{i}. File: {item['file_name']} | Similarity: {item['similarity']}")
            content_preview = json.dumps(item['content'], ensure_ascii=False)[:300]
            print(f"   ➤ Content: {content_preview}")
            print("----------------------------------------\n")
