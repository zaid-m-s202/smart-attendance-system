import pandas as pd
import os
import sys
from datetime import datetime, timedelta
import time
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_today_log_path():
    """Returns the path to today's shared attendance CSV file."""
    today    = datetime.now().strftime(config.DATE_FORMAT)
    filename = f"attendance_{today}.csv"
    return os.path.join(config.ATTENDANCE_LOG_DIR, filename)


def initialize_log(log_path):
    """Creates today's attendance CSV if it doesn't exist."""
    os.makedirs(config.ATTENDANCE_LOG_DIR, exist_ok=True)

    if not os.path.exists(log_path):
        df = pd.DataFrame(columns=["student_id", "name", "date", "time", "status", "mode"])
        df.to_csv(log_path, index=False)
        print(f"[LOG] Created new attendance log: {log_path}")


def already_marked(log_path, student_name, mode):
    """
    Returns True if a student was already marked present
    in this mode today (checks both name and mode columns).
    """
    if not os.path.exists(log_path):
        return False

    df = pd.read_csv(log_path)
    if df.empty:
        return False

    return not df[(df["name"] == student_name) & (df["mode"] == mode)].empty


def mark_attendance(student_id, student_name, mode="demo"):
    """
    Marks a student present in today's shared CSV log.
    Uses the mode column to keep demo and upload entries separate —
    a student can be Present in demo but Absent in upload on the same day.
    """
    log_path = get_today_log_path()
    initialize_log(log_path)

    if already_marked(log_path, student_name, mode):
        return False  # Already marked for this mode today

    now = datetime.now()
    new_record = pd.DataFrame([{
        "student_id" : student_id,
        "name"       : student_name,
        "date"       : now.strftime(config.DATE_FORMAT),
        "time"       : now.strftime(config.TIME_FORMAT),
        "status"     : "Present",
        "mode"       : mode
    }])

    new_record.to_csv(log_path, mode="a", header=False, index=False)
    print(f"[ATTENDANCE:{mode}] Marked present: {student_name} at {now.strftime(config.TIME_FORMAT)}")
    return True


def get_today_present(mode=None):
    """
    Returns a set of student names marked present today.
    If mode is given, filters to that mode only.
    """
    log_path = get_today_log_path()
    if not os.path.exists(log_path):
        return set()

    df = pd.read_csv(log_path)
    if df.empty:
        return set()

    if mode and "mode" in df.columns:
        df = df[df["mode"] == mode]

    return set(df["name"].values)


def clean_old_csv_logs():
    """Deletes CSV attendance logs older than CSV_RETENTION_HOURS."""
    if not os.path.exists(config.ATTENDANCE_LOG_DIR):
        return

    now     = datetime.now()
    cutoff  = now - timedelta(hours=config.CSV_RETENTION_HOURS)
    deleted = 0

    for filename in os.listdir(config.ATTENDANCE_LOG_DIR):
        if not filename.endswith(".csv"):
            continue

        filepath  = os.path.join(config.ATTENDANCE_LOG_DIR, filename)
        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

        if file_time < cutoff:
            os.remove(filepath)
            deleted += 1
            print(f"[CLEANUP] Deleted old log: {filename}")

    if deleted == 0:
        print("[CLEANUP] No old logs to delete")
    else:
        print(f"[CLEANUP] Deleted {deleted} old CSV log(s)")


def start_cleanup_scheduler():
    """Runs clean_old_csv_logs every 12 hours in a background thread."""
    def scheduler_loop():
        while True:
            print("[SCHEDULER] Running CSV cleanup...")
            clean_old_csv_logs()
            time.sleep(12 * 60 * 60)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    print("[SCHEDULER] CSV cleanup scheduler started — runs every 12 hours")


def clear_all_csv_logs():
    """Deletes all CSV logs."""
    if not os.path.exists(config.ATTENDANCE_LOG_DIR):
        print("[CLEANUP] No attendance_logs folder found")
        return

    files = [f for f in os.listdir(config.ATTENDANCE_LOG_DIR) if f.endswith(".csv")]

    if not files:
        print("[CLEANUP] No CSV logs to delete")
        return

    for filename in files:
        os.remove(os.path.join(config.ATTENDANCE_LOG_DIR, filename))
        print(f"[CLEANUP] Deleted: {filename}")

    print(f"[CLEANUP] Done — {len(files)} file(s) deleted")