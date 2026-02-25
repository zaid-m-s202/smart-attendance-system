import pandas as pd
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_today_log_path():
    """Returns the path to today's attendance CSV file."""
    today = datetime.now().strftime(config.DATE_FORMAT)
    filename = f"attendance_{today}.csv"
    return os.path.join(config.ATTENDANCE_LOG_DIR, filename)


def initialize_log(log_path):
    """Creates today's attendance CSV if it doesn't exist."""
    os.makedirs(config.ATTENDANCE_LOG_DIR, exist_ok=True)

    if not os.path.exists(log_path):
        df = pd.DataFrame(columns=["student_id", "name", "date", "time", "status"])
        df.to_csv(log_path, index=False)
        print(f"[LOG] Created new attendance log: {log_path}")


def already_marked(log_path, student_name):
    """Returns True if student was already marked present today."""
    if not os.path.exists(log_path):
        return False

    df = pd.read_csv(log_path)
    return student_name in df["name"].values


def mark_attendance(student_id, student_name):
    """
    Marks a student present in today's log.
    Prevents duplicate entries for the same student on the same day.
    """
    log_path = get_today_log_path()
    initialize_log(log_path)

    if already_marked(log_path, student_name):
        return False  # Already marked, skip

    now = datetime.now()
    new_record = pd.DataFrame([{
        "student_id" : student_id,
        "name"       : student_name,
        "date"       : now.strftime(config.DATE_FORMAT),
        "time"       : now.strftime(config.TIME_FORMAT),
        "status"     : "Present"
    }])

    new_record.to_csv(log_path, mode="a", header=False, index=False)
    print(f"[ATTENDANCE] Marked present: {student_name} at {now.strftime(config.TIME_FORMAT)}")
    return True