#!/usr/bin/env python3

import os
import zipfile
import datetime
import shutil
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

# ✅ Load .env file from same directory as this script
load_dotenv(os.path.expanduser("~/.backup_config.env"))

# Load environment variables
PROJECT_NAME = os.getenv("PROJECT_NAME")
SOURCE_DIR = os.getenv("SOURCE_DIR")
BACKUP_DIR = os.getenv("BACKUP_DIR")
LOG_FILE = os.getenv("LOG_FILE")

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", 7))
RETENTION_WEEKS = int(os.getenv("RETENTION_WEEKS", 4))
RETENTION_MONTHS = int(os.getenv("RETENTION_MONTHS", 3))

RCLONE_REMOTE = os.getenv("RCLONE_REMOTE")
RCLONE_FOLDER = os.getenv("RCLONE_FOLDER")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
NOTIFY = os.getenv("NOTIFY", "true").lower() == "true"

# Timestamp and paths
now = datetime.datetime.now()
date_path = now.strftime("%Y/%m/%d")
timestamp = now.strftime("%Y%m%d_%H%M%S")
zip_name = f"{PROJECT_NAME}_{timestamp}.zip"
zip_dir = Path(BACKUP_DIR) / date_path
zip_path = zip_dir / zip_name

# Ensure backup directory exists
os.makedirs(zip_dir, exist_ok=True)

# Create zip archive
print(f"[INFO] Creating backup: {zip_path}")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            full_path = os.path.join(root, file)
            arcname = os.path.relpath(full_path, SOURCE_DIR)
            zipf.write(full_path, arcname)

# Upload to Google Drive using rclone
upload_cmd = f"rclone copy '{zip_path}' {RCLONE_REMOTE}:{RCLONE_FOLDER}"
print(f"[INFO] Uploading to Google Drive using rclone...")
upload_status = subprocess.call(upload_cmd, shell=True)

# Logging
status_text = "Success" if upload_status == 0 else "Failed"
log_entry = f"{now} | Backup: {zip_path.name} | Upload: {status_text}\n"
with open(LOG_FILE, "a") as log:
    log.write(log_entry)

# Send notification webhook if enabled and upload was successful
if NOTIFY and upload_status == 0:
    payload = {
        "project": PROJECT_NAME,
        "date": now.isoformat(),
        "status": "BackupSuccessful"
    }
    try:
        subprocess.run([
            "curl", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload),
            WEBHOOK_URL
        ])
        print(f"[INFO] Webhook notification sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send webhook: {e}")

# Retention cleanup
def delete_old_files(path, max_days):
    now_ts = datetime.datetime.now().timestamp()
    for dirpath, _, files in os.walk(path):
        for file in files:
            file_path = Path(dirpath) / file
            if file_path.suffix != ".zip":
                continue
            age_days = (now_ts - file_path.stat().st_mtime) / (3600 * 24)
            if age_days > max_days:
                try:
                    file_path.unlink()
                    with open(LOG_FILE, "a") as log:
                        log.write(f"{datetime.datetime.now()} | Deleted: {file_path.name}\n")
                    print(f"[INFO] Deleted old backup: {file_path}")
                except Exception as e:
                    print(f"[ERROR] Could not delete {file_path}: {e}")

# Apply retention policy
max_age_days = max(RETENTION_DAYS, RETENTION_WEEKS * 7, RETENTION_MONTHS * 30)
delete_old_files(BACKUP_DIR, max_age_days)
