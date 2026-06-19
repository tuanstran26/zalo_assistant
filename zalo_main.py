from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request

from engines.executor import WorkflowExecutor
from get_history_chat import get_conversation


PORT = int(os.getenv("PORT", "5051"))
TOKENS_FILE = Path(os.environ.get("TOKENS_FILE", "tokens.json"))
OA_SEND_MESSAGE_URL = "https://openapi.zalo.me/v3.0/oa/message/cs"
MAX_ZALO_MESSAGE_LENGTH = 2000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
executor = WorkflowExecutor("workflow.yaml")
processed_msgs: set[str] = set()
processed_msgs_lock = threading.Lock()
refresh_thread_stop = threading.Event()


def load_tokens() -> dict[str, Any]:
    if not TOKENS_FILE.exists():
        raise FileNotFoundError(
            f"{TOKENS_FILE} was not found. Add an initial refresh/access token file first."
        )
    with TOKENS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def signature_from_raw_body(raw_bytes: bytes, secret: str) -> str:
    return hashlib.sha256(raw_bytes + secret.encode("utf-8")).hexdigest()


def split_text_by_space(text: str, max_len: int = MAX_ZALO_MESSAGE_LENGTH) -> list[str]:
    chunks: list[str] = []
    remaining = text or ""

    while len(remaining) > max_len:
        split_idx = remaining.rfind(" ", 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        chunks.append(remaining[:split_idx].strip())
        remaining = remaining[split_idx:].strip()

    if remaining:
        chunks.append(remaining.strip())
    return chunks


def build_workflow_input(user_id: str, text: str) -> dict[str, Any]:
    history_chat = str(get_conversation(user_id))
    return {
        "user_question": text,
        "context": {
            "conversation_history": "",
            "current_table": executor.context.get("current_table"),
            "selected_fields": executor.context.get("selected_fields", []),
        },
        "history_chat": history_chat,
    }


def generate_answer(user_id: str, text: str) -> str:
    executor.run(
        start_step_id="standardize_question",
        initial_input=build_workflow_input(user_id, text),
    )
    return str(executor.context.get("final_answer", ""))


def send_zalo_message(user_id: str, text: str) -> dict[str, Any] | None:
    access_token = load_tokens()["access_token"]
    headers = {
        "Content-Type": "application/json",
        "access_token": access_token,
    }

    final_result = None
    chunks = split_text_by_space(text)
    for index, chunk in enumerate(chunks, start=1):
        payload = {
            "recipient": {"user_id": user_id},
            "message": {"text": chunk},
        }
        response = requests.post(
            OA_SEND_MESSAGE_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        try:
            response.raise_for_status()
            final_result = response.json()
            logger.info("Sent message part %s/%s", index, len(chunks))
        except requests.RequestException:
            logger.exception(
                "Failed to send message part %s, status=%s text=%s",
                index,
                response.status_code,
                response.text,
            )
            break

    return final_result


def send_text_to_user(user_id: str, text: str) -> dict[str, Any] | None:
    answer = generate_answer(user_id, text)
    return send_zalo_message(user_id, answer)


def _is_duplicate_message(msg_id: str | None) -> bool:
    if not msg_id:
        return False
    with processed_msgs_lock:
        if msg_id in processed_msgs:
            return True
        processed_msgs.add(msg_id)
    return False


def handle_zalo_event(payload: dict[str, Any] | None) -> None:
    if not payload:
        return

    msg_id = payload.get("message", {}).get("msg_id")
    if _is_duplicate_message(msg_id):
        logger.info("Duplicate message ignored: %s", msg_id)
        return

    if payload.get("event_name") != "user_send_text":
        return

    user_id = payload["sender"]["id"]
    text = payload["message"]["text"]
    logger.info("New message from user %s", user_id)
    send_text_to_user(user_id, text)


@app.route("/", methods=["GET"])
def home():
    return "Hello from Zalo Chatbot (Flask)", 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": int(time.time())})


@app.route("/zalo/webhook", methods=["POST"])
def zalo_webhook():
    payload = request.get_json(force=True, silent=True)
    if payload is None:
        return "Bad Request", 400

    logger.info("Incoming webhook: %s", payload)
    threading.Thread(target=handle_zalo_event, args=(payload,), daemon=True).start()
    return "OK", 200


@app.route("/send", methods=["POST"])
def send_api():
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid json"}), 400

    user_id = body.get("user_id")
    text = body.get("text")
    if not user_id or not text:
        return jsonify({"error": "user_id and text required"}), 400

    try:
        response = send_text_to_user(user_id, text)
        return jsonify({"result": response})
    except Exception as exc:
        logger.exception("Failed to send manual message")
        return jsonify({"error": "failed to send", "detail": str(exc)}), 500


if __name__ == "__main__":
    try:
        try:
            from waitress import serve

            logger.info("Starting server with waitress on 0.0.0.0:%d", PORT)
            serve(app, host="0.0.0.0", port=PORT)
        except Exception:
            logger.info("Starting Flask dev server on 0.0.0.0:%d", PORT)
            app.run(host="0.0.0.0", port=PORT)
    finally:
        refresh_thread_stop.set()
        logger.info("Shutting down...")
