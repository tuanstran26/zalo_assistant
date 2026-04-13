import os
import io
import time
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

import backoff
from supabase import create_client, Client




SERVICE_ACCOUNT_FILE = "qdrant-ingestion-service.json"
FOLDER_ID = os.environ.get("FOLDER_ID")
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "./downloads"))
POLL_INTERVAL = 30

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
    raise RuntimeError("SERVICE_ACCOUNT_FILE must point to a valid service account JSON file")
if not FOLDER_ID:
    raise RuntimeError("FOLDER_ID must be set in environment")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def build_drive_service():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return service


def list_files_in_folder(service, folder_id, page_size=100):
    q = f"'{folder_id}' in parents and trashed = false"
    fields = "nextPageToken, files(id, name, mimeType, modifiedTime, size)"
    page_token = None
    items = []
    while True:
        resp = service.files().list(q=q, fields=fields, pageSize=page_size, pageToken=page_token).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def has_seen(file_id: str) -> bool:
    try:
        res = supabase.table("seen_files").select("file_id").eq("file_id", file_id).limit(1).execute()
    except Exception as e:
        logging.warning("Supabase select exception: %s", e)
        return False
    if not res or not isinstance(res, dict):
        return False
    data = res.get("data") or []
    return len(data) > 0


def insert_seen_minimal(file_id: str, name: str):
    payload = {"file_id": file_id, "name": name}
    try:
        res = supabase.table("seen_files").upsert(payload).execute()
        if isinstance(res, dict) and res.get("error"):
            logging.warning("Supabase upsert error (ignored): %s", res.get("error"))
    except Exception as e:
        logging.exception("Supabase upsert exception (ignored): %s", e)


def backoff_handler(details):
    logging.warning("Backing off {wait:0.1f}s after {tries} tries".format(**details))


@backoff.on_exception(backoff.expo, (HttpError, IOError), max_tries=5, on_backoff=backoff_handler)
def download_regular_file(service, file_id: str, tmp_path: Path):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(str(tmp_path), 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()
    return tmp_path


@backoff.on_exception(backoff.expo, (HttpError, IOError), max_tries=5, on_backoff=backoff_handler)
def export_and_download(service, file_id: str, export_mime: str, tmp_path: Path):
    request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    fh = io.FileIO(str(tmp_path), 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()
    return tmp_path


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c not in ('<', '>', ':', '"', '/', '\\', '|', '?', '*')).strip()

def process_file(service, fmeta):
    file_id = fmeta['id']
    name = fmeta.get('name', 'file')
    mime = fmeta.get('mimeType')
    modified_time = fmeta.get('modifiedTime')

    if has_seen(file_id):
        logging.debug("Skipping because supabase has record: %s", file_id)
        return

    safe_name = sanitize_filename(name)
    final_path = DOWNLOAD_DIR / safe_name
    tmp_path = final_path.with_suffix(final_path.suffix + ".part")

    if final_path.exists():
        insert_seen_minimal(file_id, name)
        print(name)
        logging.info("Local file exists, recorded in supabase and skipped download: %s", final_path)
        return

    try:
        if mime and mime.startswith("application/vnd.google-apps"):
            export_mime = "text/plain" if mime == "application/vnd.google-apps.document" else "application/pdf"
            logging.info("Exporting native Drive file %s -> %s", name, final_path)
            export_and_download(service, file_id, export_mime, tmp_path)
        else:
            logging.info("Downloading Drive file %s -> %s", name, final_path)
            download_regular_file(service, file_id, tmp_path)

        os.replace(str(tmp_path), str(final_path))

        insert_seen_minimal(file_id, name)

        print(name)
        logging.info("Downloaded and recorded file: %s", final_path)

    except Exception as e:
        logging.exception("Error downloading file %s: %s", name, e)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def main_loop():
    service = build_drive_service()
    logging.info("Starting drive poller (download-only, minimal supabase record) ...")
    while True:
        try:
            items = list_files_in_folder(service, FOLDER_ID)
            logging.info("Found %d files in folder", len(items))
            items_sorted = sorted(items, key=lambda x: x.get('modifiedTime') or "")
            for f in items_sorted:
                try:
                    process_file(service, f)
                except Exception as e:
                    logging.exception("Failed processing file %s: %s", f.get('name'), e)
        except HttpError as err:
            logging.exception("Drive API error: %s", err)
        except Exception as e:
            logging.exception("Unexpected error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
