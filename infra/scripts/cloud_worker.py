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


def should_run(now, schedule_time, last_run_key):
    if now.strftime("%H:%M") != schedule_time:
        return False
    return last_run_key != now.strftime("%Y-%m-%d")


def run_command(job_name, command, enabled=True):
    if not enabled:
        log(f"{job_name} disabled by environment.")
        return "disabled"
    log(f"Starting {job_name}.")
    try:
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            log(f"{job_name} finished.")
            return "ok"
        log(f"{job_name} finished with exit code {result.returncode}.")
        return "warning"
    except Exception as exc:
        log(f"{job_name} failed to start: {exc}")
        return "error"


def run_placeholder(job_name, reason):
    log(f"{job_name} placeholder: {reason}")
    return "placeholder"


def run_sap_sync():
    if os.getenv("SAP_SYNC_ENABLED", "false").lower() != "true":
        log("SAP sync disabled by SAP_SYNC_ENABLED.")
        return "disabled"
    return run_command("SAP nightly sync", ["python", "sync_sap_b1.py", "--trigger", "scheduled"])


def run_backup():
    backup_script = os.getenv("BACKUP_SCRIPT", "/app/backup.sh")
    if not os.path.exists(backup_script):
        return run_placeholder("Daily backup", f"{backup_script} not found in this container.")
    return run_command("Daily backup", ["bash", backup_script], os.getenv("BACKUP_ENABLED", "true").lower() == "true")


def run_knowledge_index():
    return run_placeholder("Knowledge index", "parser/vector workers are reserved; current knowledge APIs stay available.")


def run_daily_report():
    return run_placeholder("Daily business report", "AI report generation is prepared; final report requires real data and review.")


def run_web_research():
    if os.getenv("WEB_SEARCH_ENABLED", "false").lower() != "true":
        log("Web research disabled by WEB_SEARCH_ENABLED.")
        return "disabled"
    return run_placeholder("Web research", "search provider is configured later; human review required before saving knowledge.")


def run_weekly_report():
    return run_placeholder("Weekly report", "weekly report template is prepared; automated generation awaits real BI data.")


def run_monthly_report():
    return run_placeholder("Monthly report", "monthly report template is prepared; automated generation awaits real BI data.")


def should_run_weekly(now, weekly_time, last_key):
    parts = weekly_time.split()
    if len(parts) != 2:
        return False
    day, clock = parts[0].upper(), parts[1]
    day_map = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    if day not in day_map:
        return False
    if now.weekday() != day_map.index(day) or now.strftime("%H:%M") != clock:
        return False
    return last_key != now.strftime("%Y-%m-%d")


def should_run_monthly(now, day, last_key):
    try:
        target_day = int(day)
    except Exception:
        target_day = 1
    if now.day != target_day or now.strftime("%H:%M") != os.getenv("MONTHLY_REPORT_TIME", "09:00"):
        return False
    return last_key != now.strftime("%Y-%m")


def main():
    jobs = [
        ("sap_sync", os.getenv("SAP_SYNC_TIME", "22:00"), run_sap_sync),
        ("knowledge_index", os.getenv("KNOWLEDGE_INDEX_TIME", "02:00"), run_knowledge_index),
        ("backup", os.getenv("BACKUP_TIME", "02:30"), run_backup),
        ("daily_report", os.getenv("DAILY_REPORT_TIME", "08:00"), run_daily_report),
        ("web_research", os.getenv("WEB_RESEARCH_TIME", "10:00"), run_web_research),
    ]
    last_runs = {}
    log("FoxBrain V6 worker started. Jobs: " + ", ".join(f"{name}@{clock}" for name, clock, _ in jobs))
    while True:
        now = datetime.now()
        for name, clock, runner in jobs:
            if should_run(now, clock, last_runs.get(name, "")):
                status = runner()
                last_runs[name] = now.strftime("%Y-%m-%d")
                log(f"{name} status: {status}")
        if should_run_weekly(now, os.getenv("WEEKLY_REPORT_TIME", "MON 09:00"), last_runs.get("weekly_report", "")):
            status = run_weekly_report()
            last_runs["weekly_report"] = now.strftime("%Y-%m-%d")
            log(f"weekly_report status: {status}")
        if should_run_monthly(now, os.getenv("MONTHLY_REPORT_DAY", "1"), last_runs.get("monthly_report", "")):
            status = run_monthly_report()
            last_runs["monthly_report"] = now.strftime("%Y-%m")
            log(f"monthly_report status: {status}")
        time.sleep(60)


if __name__ == "__main__":
    main()
