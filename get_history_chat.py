import os
import requests
import json

API_URL = "https://openapi.zalo.me/v2.0/oa/message/history"
OA_ID = os.environ.get("OA_ID") 
TOKENS_FILE = os.environ.get("TOKENS_FILE", "tokens.json")



def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print("⚠️ Không tìm thấy file tokens.json — bạn cần có refresh_token ban đầu.")
        return None


def get_conversation(user_id: str, count: int = 10, offset: int = 0):
    
    tokens = load_tokens()

    access_token = tokens["access_token"]

    params = {
        "data": json.dumps({
            "user_id": user_id,
            "offset": offset,
            "count": count
        }, ensure_ascii=False)
    }
    headers = {"access_token": access_token}

    response = requests.get(API_URL, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    if data.get("error") != 0:
        raise ValueError(f"Lỗi từ API Zalo: {data}")

    messages = data.get("data", [])
    if not messages:
        return "[]"

    messages.sort(key=lambda m: m.get("time", 0))

    conversations = []
    current_bot_msgs = []
    last_user_msg = None

    for msg in messages:
        from_id = msg.get("from_id")
        text = msg.get("message", "").strip()
        if not text:
            continue

        if from_id == OA_ID:
            current_bot_msgs.append(text)
        else:
           
            if last_user_msg is not None:
                conversations.append({
                    "user_request": last_user_msg,
                    "llm_response": "\n".join(current_bot_msgs) if current_bot_msgs else ""
                })
                current_bot_msgs = []

            last_user_msg = text

    if last_user_msg is not None:
        conversations.append({
            "user_request": last_user_msg,
            "llm_response": "\n".join(current_bot_msgs) if current_bot_msgs else ""
        })

    return json.dumps(conversations, ensure_ascii=False)


if __name__ == "__main__":
    user_id = "2301926699902886075"  
    try:
        result = get_conversation(user_id)
        print("✅ Kết quả sau khi xử lý:")
        print(result)
    except Exception as e:
        print("❌ Lỗi:", e)
