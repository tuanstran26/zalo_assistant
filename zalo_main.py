
import hmac
import os
import json
import time
import hashlib
import logging
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify
import requests
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam
import threading
from engines.executor import WorkflowExecutor
from get_history_chat import get_conversation


_refresh_lock = threading.Lock()

PORT = 5051



OAUTH_REFRESH_URL = "https://oauth.zaloapp.com/v4/oa/access_token"
OA_SEND_MESSAGE_URL = "https://openapi.zalo.me/v3.0/oa/message/cs"

processed_msgs = set()


TOKENS_FILE = os.environ.get("TOKENS_FILE", "tokens.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

executor = WorkflowExecutor("workflow.yaml")

refresh_thread_stop = threading.Event()

def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print("Không tìm thấy file tokens.json — bạn cần có refresh_token ban đầu.")
        return None



def signature_from_raw_body(raw_bytes: bytes, secret: str) -> str:
    return hashlib.sha256(raw_bytes + secret.encode("utf-8")).hexdigest()


def send_text_to_user(user_id: str, text: str) -> Dict[str, Any]:
    tokens = load_tokens()

    access_token = tokens["access_token"]
    print("access token",access_token)
    headers = {
        "Content-Type": "application/json",
        "access_token": access_token
    }
    conversation_history = []

    history_chat = str(get_conversation(user_id))

    executor.run(
        start_step_id="standardize_question",
        initial_input={
            "user_question": text,
            "context": {
                "conversation_history": "\n".join(conversation_history),
                "current_table": executor.context.get("current_table"),
                "selected_fields": executor.context.get("selected_fields", []),
            },
            "history_chat": history_chat
        }
    )

    response = executor.context.get("final_answer")

    MAX_LENGTH = 2000

    def split_text_by_space(text: str, max_len: int):
        chunks = []
        while len(text) > max_len:
            split_idx = text.rfind(" ", 0, max_len)
            if split_idx == -1:
                split_idx = max_len 
            chunks.append(text[:split_idx].strip())
            text = text[split_idx:].strip()
        if text:
            chunks.append(text.strip())
        return chunks

    responses = split_text_by_space(response, MAX_LENGTH)

    final_result = None
    for idx, chunk in enumerate(responses, start=1):
        payload = {
            "recipient": {"user_id": user_id},
            "message": {"text": chunk}
        }

        resp = requests.post(OA_SEND_MESSAGE_URL, headers=headers, json=payload, timeout=15)
        try:
            resp.raise_for_status()
            final_result = resp.json()
            print(f"Sent part {idx}/{len(responses)} ({len(chunk)} chars)")
        except Exception:
            logging.exception("Failed to send message part %d, status=%s text=%s",
                              idx, resp.status_code, resp.text)
            break

    return final_result


def handle_zalo_event(payload):
    msg_id = payload.get("message", {}).get("msg_id")
    if msg_id in processed_msgs:
        logging.info(f"Duplicate message ignored: {msg_id}")
        return
    processed_msgs.add(msg_id)

    event = payload.get("event_name")

    if event == "user_send_text":
        user_id = payload["sender"]["id"]
        text = payload["message"]["text"]

        logging.info(f"Tin nhắn mới từ user {user_id}: {text}")

        reply = f"Bạn vừa gửi: {text}"  

        send_text_to_user(user_id, reply)

@app.route("/", methods=["GET"])
def home():
    return "Hello from Zalo Chatbot (Flask)", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": int(time.time())})


@app.route("/zalo/webhook", methods=["POST"])
def zalo_webhook():
    payload = request.get_json()
    logging.info("Incoming webhook: %s", payload)
    try:
        payload = request.get_json(force=True, silent=True)
    except Exception:
        return "Bad Request", 400
    threading.Thread(target=handle_zalo_event, args=(payload,), daemon=True).start()
    return "OK", 200



@app.route("/send", methods=["POST"])
def send_api():
    """
    Manual send API (useful to test sending message to user):
    POST body: { "user_id": "...", "text": "..." }
    """
    print(request.json)
    try:
        body = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400
    user_id = body.get("user_id")
    text = body.get("text")
    if not user_id or not text:
        return jsonify({"error": "user_id and text required"}), 400
    try:
        resp = send_text_to_user(user_id, text)
        return jsonify({"result": resp})
    except Exception as e:
        return jsonify({"error": "failed to send", "detail": str(e)}), 500





if __name__ == "__main__":
  

    try:
        try:
            from waitress import serve
            logging.info("Starting server with waitress on 0.0.0.0:%d", PORT)
            serve(app, host="0.0.0.0", port=PORT)
        except Exception:
            logging.info("Starting Flask dev server on 0.0.0.0:%d", PORT)
            app.run(host="0.0.0.0", port=PORT)
    finally:
        refresh_thread_stop.set()
        logging.info("Shutting down...")
