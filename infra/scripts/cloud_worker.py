import os
import subprocess
import time
from datetime import datetime


def log(message):
    os.makedirs("/app/logs", exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line, flush=True)
    with open("/app/logs/worker.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def should_run(now, sync_time, last_run_date):
    if now.strftime("%H:%M") != sync_time:
        return False
    return last_run_date != now.strftime("%Y-%m-%d")


def run_sap_sync():
    if os.getenv("SAP_SYNC_ENABLED", "false").lower() != "true":
        log("SAP sync disabled by SAP_SYNC_ENABLED.")
        return
    log("Starting scheduled SAP sync.")
    try:
        subprocess.run(["python", "sync_sap_b1.py", "--trigger", "scheduled_22_00"], check=False)
    except Exception as exc:
        log(f"SAP sync failed to start: {exc}")


def main():
    sync_time = os.getenv("SAP_SYNC_TIME", "22:00")
    last_run_date = ""
    log(f"FoxBrain worker started. SAP sync time: {sync_time}")
    while True:
        now = datetime.now()
        if should_run(now, sync_time, last_run_date):
            run_sap_sync()
            last_run_date = now.strftime("%Y-%m-%d")
        time.sleep(60)


if __name__ == "__main__":
    main()
