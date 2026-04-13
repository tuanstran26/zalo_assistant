import json
from flask import Flask, request, jsonify
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import io
from extract_text import extract_text_with_metadata  



CREDENTIALS_FILE = "qdrant-ingestion-service.json"
DOWNLOAD_DIR = "downloads"  

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)


@app.route("/drive-webhook", methods=["POST"])
def drive_webhook():
    print("Received webhook:", request.data)
    data = request.get_json()
    if not data or "fileId" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    file_id = data["fileId"]
    file_name = data.get("fileName", file_id)

    try:
      
        request_drive = drive_service.files().get_media(fileId=file_id)
        file_path = os.path.join(DOWNLOAD_DIR, file_name)
        with io.FileIO(file_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request_drive)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"Download {int(status.progress() * 100)}%.")

        print(f"File downloaded: {file_path}")
        print("Now extracting file")


        return jsonify({"status": "success", "file": file_path}), 200
    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5090, threaded=True)  