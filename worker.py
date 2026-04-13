import os
import time
import traceback
from pathlib import Path
from extract_text import extract_text_with_metadata

DOWNLOAD_DIR = "downloads"
PROCESSED_DIR = "processed"
FAILED_DIR = "failed"

for d in [PROCESSED_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)


def process_file(file_name):
    print(f"Bắt đầu xử lý: {file_name}")
    extract_text_with_metadata(file_name)
    print(f"Xử lý xong: {file_name}")


def main_loop():
    print("Worker đang chạy, chờ file mới trong thư mục downloads/...")
    while True:
        try:
            files = sorted(Path(DOWNLOAD_DIR).glob("*"))  
            if not files:
                time.sleep(2)
                continue

            for file_path in files:
                try:
                    file_name = os.path.basename(file_path)
                    process_file(file_name)
                    target = Path(PROCESSED_DIR) / file_path.name
                    file_path.rename(target)
                except Exception as e:
                    traceback.print_exc()
                    target = Path(FAILED_DIR) / file_path.name
                    file_path.rename(target)
        except KeyboardInterrupt:
            print("Dừng worker")
            break
        except Exception as e:
            print(f"Lỗi vòng lặp: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main_loop()
