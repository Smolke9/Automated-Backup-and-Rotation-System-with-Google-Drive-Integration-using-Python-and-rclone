# Automated Backup & Rotation System with Google Drive Integration

**Using:** Python · rclone · cron · Webhook Notifications

---

## Project Overview
This project automates backing up local directories by compressing them into timestamped `.zip` files and uploading them to Google Drive using `rclone`. It features retention (daily/weekly/monthly), webhook notifications, and detailed logging. Configuration is controlled through a `.env` file and the system runs automatically via a cron job.

## Features
- Create timestamped `.zip` backups of specified directories
- Upload backups to Google Drive via `rclone` (remote: `gdrive-backup`)
- Retention policy for old backups (daily/weekly/monthly rotation)
- Webhook notifications for success/failure
- Detailed logging of all operations
- Cron-triggered automation; virtualenv-aware runner script

## Project Structure
```
backup_project/
├── backups/               # Local .zip files before upload
├── logs/                  # Log files
├── venv/                  # Python virtual environment
├── backup_script.py       # Main Python backup script
├── run_backup.sh          # Shell wrapper for cron
└── .backup_config.env     # Environment/configuration file (example name)
```

## Requirements
- Python 3.8+
- `python-dotenv` (`pip install python-dotenv`)
- `rclone` (configured remote `gdrive-backup`)
- `zip` / `unzip` utilities (Linux: `sudo apt install zip unzip -y`)
- `curl` (for webhook testing)
- `cron` (for scheduled runs)

## Quick Setup
1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install python-dotenv
```

2. Install `rclone` and configure your Google Drive remote named `gdrive-backup`:
```bash
curl https://rclone.org/install.sh | sudo bash
rclone config
# During config: set Remote Name = gdrive-backup, Storage = Google Drive, Scope = full access, etc.
```

3. Create directories:
```bash
mkdir -p backup_project/{backups,logs}
```

4. Place this README inside `backup_project/` and add the provided scripts (`backup_script.py`, `run_backup.sh`) and `.backup_config.env` as described below.

## Example `.backup_config.env`
```env
# Path to the directory you want to backup (absolute preferred)
SOURCE_DIR=/home/ubuntu/my_project

# Local backups folder (relative or absolute)
BACKUP_DIR=/home/ubuntu/backup_project/backups

# Google Drive folder (remote:path). If empty uploads to remote root
GDRIVE_FOLDER=backups/my_project

# rclone remote name
RCLONE_REMOTE=gdrive-backup

# Retention (days) — cleanup local & remote according to these thresholds
RETENTION_DAYS_DAILY=7
RETENTION_DAYS_WEEKLY=30
RETENTION_DAYS_MONTHLY=365

# Webhook URL for notifications (optional)
WEBHOOK_URL=https://webhook.site/your-webhook-id

# Log file
LOG_FILE=/home/ubuntu/backup_project/logs/backup.log

# Optional: extra rclone flags (e.g. --drive-chunk-size 64M)
RCLONE_FLAGS=--progress
```

> Save this as `~/.backup_config.env` or in `backup_project/.backup_config.env` (update `run_backup.sh` accordingly).

## Suggested `backup_script.py` (summary)
- Load environment via `dotenv`
- Validate paths, create timestamps
- Create a `.zip` archive in `backups/` (e.g. `projectname_YYYYmmdd_HHMMSS.zip`)
- Upload with `rclone copy` to `${RCLONE_REMOTE}:${GDRIVE_FOLDER}`
- Send success/failure webhook payload (HTTP POST JSON)
- Log each step and errors to `LOG_FILE`
- Remove local temp files on success
- Enforce retention: remove local and remote files older than thresholds

> **Tip:** Use `subprocess.run([...], check=True)` for `rclone` calls and capture output for logs.

### Example webhook payloads
```json
# Success
{"status":"success","file":"projectname_20251125_150102.zip","size_bytes":1234567,"uploaded_to":"gdrive-backup:backups/my_project"}

# Failure
{"status":"failed","error":"rclone returned exit code 1","file":"projectname_20251125_150102.zip"}
```

## `run_backup.sh` (for cron)
Wraps environment activation and calls the Python script. Example:
```bash
#!/usr/bin/env bash
# Absolute path to project and venv
PROJECT_DIR="/home/ubuntu/backup_project"
source "$PROJECT_DIR/venv/bin/activate"

# Load environment config
if [ -f "$HOME/.backup_config.env" ]; then
  source "$HOME/.backup_config.env"
fi

cd "$PROJECT_DIR" || exit 1
python3 "$PROJECT_DIR/backup_script.py" >> "$PROJECT_DIR/logs/cron_run.log" 2>&1
```

Make it executable:
```bash
chmod +x run_backup.sh
```

## Cron Example
Edit crontab with `crontab -e` and add (for testing every minute):
```
* * * * * /home/ubuntu/backup_project/run_backup.sh >> /home/ubuntu/backup_project/cron_output.log 2>&1
```
For production, schedule daily at 02:00 AM:
```
0 2 * * * /home/ubuntu/backup_project/run_backup.sh >> /home/ubuntu/backup_project/cron_output.log 2>&1
```

## Retention Policy (concept)
- **Daily**: keep last `RETENTION_DAYS_DAILY` days
- **Weekly**: keep one backup per week for `RETENTION_DAYS_WEEKLY` days
- **Monthly**: keep one per month for `RETENTION_DAYS_MONTHLY` days

Implementation approach:
- Parse timestamps from filenames
- Classify backups as daily/weekly/monthly and decide which to keep and which to delete
- Use `rclone delete` / `rclone purge` to remove remote files when needed

## Testing & Manual Run
1. Run manually:
```bash
source venv/bin/activate
python3 backup_script.py
```

2. Verify:
- A zip file appears in `backups/`
- `rclone` uploads the file to Google Drive
- Webhook (if configured) receives notification
- `logs/backup.log` contains a record of the run

## Troubleshooting
- **rclone auth issues**: run `rclone config` and re-authorize with the browser login flow.
- **Permission errors**: confirm file permissions and that cron user has access to files/venv.
- **Large files fail**: increase `--drive-chunk-size` in `RCLONE_FLAGS` or use service account for larger throughput.
- **Webhook failures**: use `curl -v` to test the webhook endpoint manually.

## Security & Best Practices
- Keep your `.backup_config.env` outside version control (add to `.gitignore`).
- Limit access to Google Drive remote where possible (use service accounts for automated servers).
- Encrypt sensitive backups if they contain secrets (e.g., use `gpg` before uploading).
- Monitor storage usage on Google Drive and set alerts.

## Example: Minimal `backup_script.py`
Below is a compact, practical starting point for `backup_script.py`. Customize as needed.
```python
#!/usr/bin/env python3
import os, sys, subprocess, zipfile, json, time, logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv(os.path.expanduser('~/.backup_config.env'))

SOURCE_DIR = os.getenv('SOURCE_DIR')
BACKUP_DIR = os.getenv('BACKUP_DIR', './backups')
RCLONE_REMOTE = os.getenv('RCLONE_REMOTE', 'gdrive-backup')
GDRIVE_FOLDER = os.getenv('GDRIVE_FOLDER', '').strip('/')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
LOG_FILE = os.getenv('LOG_FILE', './logs/backup.log')
RCLONE_FLAGS = os.getenv('RCLONE_FLAGS', '')

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')

def make_zip(source_path, dest_dir):
    base = os.path.basename(os.path.abspath(source_path.rstrip('/')))
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    fname = f\"{base}_{ts}.zip\"
    out_path = os.path.join(dest_dir, fname)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.isfile(source_path):
            zf.write(source_path, arcname=os.path.basename(source_path))
        else:
            for root, _, files in os.walk(source_path):
                for f in files:
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, start=os.path.dirname(source_path))
                    zf.write(full, arcname=arc)
    return out_path

def rclone_upload(local_path):
    remote_path = f\"{RCLONE_REMOTE}:{GDRIVE_FOLDER}\" if GDRIVE_FOLDER else f\"{RCLONE_REMOTE}:\"
    cmd = ['rclone', 'copy', local_path, remote_path] + (RCLONE_FLAGS.split() if RCLONE_FLAGS else [])
    logging.info('Uploading %s to %s', local_path, remote_path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def send_webhook(payload):
    if not WEBHOOK_URL:
        return
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        logging.warning('Webhook failed: %s', e)

def main():
    if not SOURCE_DIR:
        logging.error('SOURCE_DIR not configured. Exiting.')
        sys.exit(1)
    try:
        zipped = make_zip(SOURCE_DIR, BACKUP_DIR)
        size = os.path.getsize(zipped)
        rc, out, err = rclone_upload(zipped)
        if rc == 0:
            logging.info('Upload successful: %s (%d bytes)', zipped, size)
            send_webhook({'status':'success','file':os.path.basename(zipped),'size_bytes':size,'uploaded_to':f\"{RCLONE_REMOTE}:{GDRIVE_FOLDER}\"})
        else:
            logging.error('Upload failed: %s', err)
            send_webhook({'status':'failed','file':os.path.basename(zipped),'error':err})
    except Exception as e:
        logging.exception('Backup failed: %s', e)
        send_webhook({'status':'failed','error':str(e)})

if __name__ == '__main__':
    main()
```


