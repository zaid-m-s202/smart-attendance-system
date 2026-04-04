import sqlite3
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ══════════════════════════════════════════════════════════════
# CONNECTION HELPERS
# ══════════════════════════════════════════════════════════════

DB_PATHS = {
    "demo"    : config.DEMO_DB_PATH,
    "upload"  : config.UPLOAD_DB_PATH,
    "lecture" : config.LECTURE_DB_PATH,
}


def get_db(mode):
    """Returns a sqlite3 connection for the given mode (demo/upload/lecture)."""
    path = DB_PATHS[mode]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════
# INIT — called once on app startup
# ══════════════════════════════════════════════════════════════

def _init_one_db(mode):
    conn   = get_db(mode)
    cursor = conn.cursor()

    # sessions table — replaces old "lectures" table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            subject      TEXT,
            date         TEXT NOT NULL,
            start_time   TEXT NOT NULL,
            end_time     TEXT,
            total_photos INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'ongoing'
        )
    """)

    # attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT NOT NULL,
            session_id      INTEGER NOT NULL,
            photos_detected INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'Absent',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(student_id, session_id)
        )
    """)

    # photo_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL,
            photo_num   INTEGER NOT NULL,
            student_id  TEXT NOT NULL,
            confidence  REAL,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] {mode}.db initialized")


def initialize_all_databases():
    """Creates all three databases and their tables. Safe to call multiple times."""
    for mode in ("demo", "upload", "lecture"):
        _init_one_db(mode)
    print("[DB] All databases ready")


# ══════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════

def create_session(mode, subject=None):
    """
    Opens a new attendance session in the given mode's database.
    Returns the new session_id.
    """
    conn   = get_db(mode)
    cursor = conn.cursor()

    now = datetime.now()
    cursor.execute("""
        INSERT INTO sessions (subject, date, start_time, status)
        VALUES (?, ?, ?, 'ongoing')
    """, (
        subject or config.SUBJECT_NAME,
        now.strftime(config.DATE_FORMAT),
        now.strftime(config.TIME_FORMAT),
    ))

    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"[DB:{mode}] Session created — ID: {session_id}")
    return session_id


def close_session(mode, session_id, total_photos, students_df, detection_counts):
    """
    Closes a session, sets total_photos + end_time, and writes final
    attendance rows for every student (Present / Absent).
    detection_counts: dict of { student_name: int }
    """
    conn   = get_db(mode)
    cursor = conn.cursor()

    now = datetime.now()

    # Update session metadata
    cursor.execute("""
        UPDATE sessions
        SET end_time = ?, total_photos = ?, status = 'completed'
        WHERE id = ?
    """, (now.strftime(config.TIME_FORMAT), total_photos, session_id))

    # Decide threshold based on mode
    threshold_map = {
        "demo"    : config.DEMO_THRESHOLD,
        "upload"  : config.UPLOAD_THRESHOLD,
        "lecture" : config.LECTURE_THRESHOLD,
    }
    threshold = threshold_map.get(mode, config.PRESENT_THRESHOLD)

    # Write attendance row per student
    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)
        status     = "Present" if count >= threshold else "Absent"

        cursor.execute("""
            INSERT INTO attendance (student_id, session_id, photos_detected, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id, session_id)
            DO UPDATE SET photos_detected = excluded.photos_detected,
                          status          = excluded.status
        """, (student_id, session_id, count, status))

    conn.commit()
    conn.close()
    print(f"[DB:{mode}] Session {session_id} closed — attendance finalized")


# ══════════════════════════════════════════════════════════════
# PHOTO LOGGING
# ══════════════════════════════════════════════════════════════

def log_photo_detection(mode, session_id, photo_num, student_id, confidence):
    """Records that a student was detected in a specific photo."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    now = datetime.now()
    cursor.execute("""
        INSERT INTO photo_log (session_id, photo_num, student_id, confidence, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, photo_num, str(student_id), confidence,
          now.strftime(config.TIME_FORMAT)))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
# QUERY HELPERS — used by Flask routes
# ══════════════════════════════════════════════════════════════

def get_all_sessions(mode):
    """Returns all sessions for a given mode, newest first."""
    conn   = get_db(mode)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM sessions ORDER BY date DESC, start_time DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_attendance(mode, session_id):
    """Returns attendance records for a specific session."""
    conn   = get_db(mode)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_id, photos_detected, status
        FROM attendance
        WHERE session_id = ?
        ORDER BY student_id
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_history(mode, student_id):
    """
    Returns all session records for a student in a given mode.
    Each row includes session metadata + attendance details.
    """
    conn   = get_db(mode)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.date, s.start_time, s.subject, s.total_photos,
               a.photos_detected, a.status
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        WHERE a.student_id = ?
        ORDER BY s.date DESC, s.start_time DESC
    """, (str(student_id),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_stats(mode, student_id):
    """
    Returns summary stats for a student in a given mode.
    { present, absent, total, percentage }
    """
    conn   = get_db(mode)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status FROM attendance WHERE student_id = ?
    """, (str(student_id),))
    rows    = cursor.fetchall()
    conn.close()

    total   = len(rows)
    present = sum(1 for r in rows if r["status"] == "Present")
    absent  = total - present
    pct     = round((present / total) * 100, 1) if total > 0 else 0.0

    return {
        "present"    : present,
        "absent"     : absent,
        "total"      : total,
        "percentage" : pct,
    }