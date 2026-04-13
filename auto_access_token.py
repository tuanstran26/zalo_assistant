import time
import json
import requests
import os



ZALO_TOKEN_URL = "https://oauth.zaloapp.com/v4/oa/access_token"
APP_ID = os.getenv("APP_ID")
SECRET_KEY = os.getenv("SECRET_KEY")
TOKENS_FILE = "tokens.json"
REFRESH_INTERVAL = 80000          


def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print("Không tìm thấy file tokens.json — bạn cần có refresh_token ban đầu.")
        return None


def save_tokens(data):
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("Đã lưu token mới vào tokens.json")


def refresh_token(old_refresh_token):
    data = {
        "refresh_token": old_refresh_token,
        "app_id": APP_ID,
        "grant_type": "refresh_token"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "secret_key": SECRET_KEY
    }

    print("Đang làm mới access token...")

    try:
        response = requests.post(ZALO_TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()

        if "access_token" in token_data:
            save_tokens(token_data)
            print(f"Access token mới: {token_data['access_token'][:20]}...")
            return token_data
        else:
            print("Lỗi khi lấy token:", token_data)
            return None

    except requests.exceptions.RequestException as e:
        print("Lỗi kết nối:", e)
        return None


def main():
    while True:
        tokens = load_tokens()
        if not tokens or "refresh_token" not in tokens:
            print("Không có refresh_token hợp lệ trong tokens.json.")
            break

        new_tokens = refresh_token(tokens["refresh_token"])
        if not new_tokens:
            print("Không thể cập nhật token, thử lại sau 10 phút.")
            time.sleep(600)
            continue

        print(f"Sẽ làm mới token sau {REFRESH_INTERVAL} giây...")
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
