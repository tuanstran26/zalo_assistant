import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any

from transformers import AutoTokenizer
from langchain_huggingface import HuggingFaceEmbeddings
from supabase import create_client

# ============================
# Config
# ============================
SUPABASE_TABLE = "vector_store_table"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
embed_token = os.getenv("EMBED_TOKEN")

EMBED_MODEL_NAME = "BAAI/bge-m3"
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cpu")
CHUNK_TOKEN_SIZE = int(os.getenv("CHUNK_TOKEN_SIZE", "300"))
CHUNK_MIN_CHARS = int(os.getenv("CHUNK_MIN_CHARS", "30"))
OVERLAP_SENTENCES = int(os.getenv("OVERLAP_SENTENCES", "1"))


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
embed_model = HuggingFaceEmbeddings(model_name=EMBED_MODEL_NAME, model_kwargs={"device": EMBED_DEVICE})

try:
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_NAME, use_fast=True)
except Exception:
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_NAME, use_fast=False)



def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def clean_text(raw_text: str) -> str:
    cleaned = re.sub(r'^\s*(\.\s*){3,}\s*$', '', raw_text, flags=re.MULTILINE)
    cleaned = re.sub(r'(?<!\n)\n(?!\n)', ' ', cleaned.strip())
    return cleaned


def preprocess_text(text: str) -> str:
    text = re.sub(r'(?:Page|Trang)?\s*-?\s*\d+\s*-?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[^\w\s.,!?%\-–()/:;\'"–—–…]', '', text, flags=re.UNICODE)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r',{2,}', ',', text)
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    return text.strip()


def sent_tokenize(text: str) -> List[str]:
    text = text.replace("\n", ". ")
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text_sentence_aware(
    text: str,
    chunk_token_size: int = CHUNK_TOKEN_SIZE,
    min_chars: int = CHUNK_MIN_CHARS,
    overlap_sentences: int = OVERLAP_SENTENCES
) -> List[str]:
   
    sentences = sent_tokenize(text)
    if not sentences:
        return []

    try:
        enc = tokenizer(sentences, add_special_tokens=False)
        sent_token_counts = [len(ids) for ids in enc["input_ids"]]
    except Exception:
        sent_token_counts = [max(1, len(s) // 4) for s in sentences]

    chunks = []
    current, current_tokens = [], 0

    def flush():
        nonlocal current, current_tokens
        if current:
            chunk_str = " ".join(current).strip()
            if len(chunk_str) >= min_chars:
                chunks.append(chunk_str)
        current, current_tokens = [], 0

    for i, (s, s_tokens) in enumerate(zip(sentences, sent_token_counts)):
        if s_tokens > chunk_token_size:
            max_chars = chunk_token_size * 4
            parts = [s[j:j+max_chars].strip() for j in range(0, len(s), max_chars)]
            for p in parts:
                flush()
                if len(p) >= min_chars:
                    chunks.append(p)
            continue

        if current_tokens + s_tokens <= chunk_token_size:
            current.append(s)
            current_tokens += s_tokens
        else:
            flush()
            if overlap_sentences > 0 and len(chunks) > 0:
                overlap = sentences[max(0, i - overlap_sentences):i]
                current = overlap.copy()
                current_tokens = sum(sent_token_counts[max(0, i - overlap_sentences):i])
            else:
                current = []
                current_tokens = 0
            current.append(s)
            current_tokens += s_tokens

    flush()
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    return embed_model.embed_documents(texts)


def process_document_and_store(doc_json: Dict[str, Any]) -> Dict[str, Any]:
  
    metadata = doc_json.get("metadata", {})
    raw_content = doc_json.get("content", "")

    text = preprocess_text(clean_text(raw_content))
    if not text:
        return {"status": "error", "message": "No text after preprocessing"}

    t0 = time.time()
    chunks = chunk_text_sentence_aware(text)
    print(f"[Chunking] {len(chunks)} chunks created in {time.time() - t0:.2f}s")

    if not chunks:
        return {"status": "error", "message": "No chunks created"}


    t1 = time.time()
    vectors = embed_texts(chunks)
    print(f"[Embedding] Done in {time.time() - t1:.2f}s")

    rows = []
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors), start=1):
        rows.append({
            "content": chunk,
            "embedding": vec,
            "metadata": {**metadata, "chunk_index": idx, "chunk_total": len(chunks)},
            "created_at": _now_iso()
        })

    supabase.table(SUPABASE_TABLE).insert(rows).execute()

    return {"status": "success", "message": f"Inserted {len(rows)} chunks", "chunks": len(rows)}
