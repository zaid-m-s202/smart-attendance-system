import sqlite3
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ══════════════════════════════════════════════════════════════
# DATABASE PATHS
# ══════════════════════════════════════════════════════════════

DB_PATHS = {
    "demo"    : os.path.join(config.BASE_DIR, "data", "demo.db"),
    "lecture" : os.path.join(config.BASE_DIR, "data", "lecture.db"),
    "upload"  : os.path.join(config.BASE_DIR, "data", "upload.db"),
}


# ══════════════════════════════════════════════════════════════
# CONNECTION HELPER
# ══════════════════════════════════════════════════════════════

def get_db(mode):
    """Returns a sqlite3 connection for the given mode."""
    if mode not in DB_PATHS:
        raise ValueError(f"[DB] Invalid mode: '{mode}' — must be demo, lecture, or upload")
    path = DB_PATHS[mode]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════
# INITIALIZATION
# ══════════════════════════════════════════════════════════════

def _init_one_db(mode):
    """Creates tables for a single mode database."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mode         TEXT NOT NULL,
            subject      TEXT,
            date         TEXT NOT NULL,
            start_time   TEXT NOT NULL,
            end_time     TEXT,
            total_photos INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'ongoing'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL,
            student_id      TEXT NOT NULL,
            name            TEXT,
            photos_detected INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'Absent',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(student_id, session_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            photo_num  INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            confidence REAL,
            timestamp  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] {mode}.db initialized")


def initialize_all_databases():
    """Creates all three mode databases and their tables."""
    for mode in ("demo", "lecture", "upload"):
        _init_one_db(mode)
    print("[DB] All databases ready")


# ══════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════

def create_session(mode, subject=None):
    """
    Creates a new session row and returns its id.
    Called at the start of demo, lecture, or upload.
    """
    conn   = get_db(mode)
    cursor = conn.cursor()
    now    = datetime.now()

    cursor.execute("""
        INSERT INTO sessions (mode, subject, date, start_time, status)
        VALUES (?, ?, ?, ?, 'ongoing')
    """, (
        mode,
        subject or mode.capitalize(),
        now.strftime(config.DATE_FORMAT),
        now.strftime(config.TIME_FORMAT)
    ))

    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"[DB] Session created — mode={mode}, id={session_id}")
    return session_id


def close_session(mode, session_id, total_photos, students_df, detection_counts):
    """
    Closes a session: sets end_time, total_photos, status=completed.
    Writes final attendance rows for every student including name.
    """
    conn   = get_db(mode)
    cursor = conn.cursor()
    now    = datetime.now()

    thresholds = {
        "demo"    : config.DEMO_THRESHOLD,
        "lecture" : config.LECTURE_THRESHOLD,
        "upload"  : config.UPLOAD_THRESHOLD,
    }
    threshold = thresholds.get(mode, 3)

    # ── Close the session row ───────────────────────────────────
    cursor.execute("""
        UPDATE sessions
        SET end_time = ?, total_photos = ?, status = 'completed'
        WHERE id = ?
    """, (now.strftime(config.TIME_FORMAT), total_photos, session_id))

    # ── Write attendance for every student ──────────────────────
    for _, student in students_df.iterrows():
        student_id = str(student["student_id"])
        name       = student["name"]
        count      = detection_counts.get(name, 0)
        status     = "Present" if count >= threshold else "Absent"

        cursor.execute("""
            INSERT INTO attendance (session_id, student_id, name, photos_detected, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, session_id)
            DO UPDATE SET photos_detected = excluded.photos_detected,
                          status          = excluded.status,
                          name            = excluded.name
        """, (session_id, student_id, name, count, status))

    conn.commit()
    conn.close()
    print(f"[DB] Session {session_id} closed — mode={mode}")


# ══════════════════════════════════════════════════════════════
# PHOTO LOGGING
# ══════════════════════════════════════════════════════════════

def log_photo_detection(mode, session_id, photo_num, student_id, confidence):
    """Records a single face detection event inside a session."""
    conn   = get_db(mode)
    cursor = conn.cursor()
    now    = datetime.now()

    cursor.execute("""
        INSERT INTO photo_log (session_id, photo_num, student_id, confidence, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, photo_num, student_id, confidence,
          now.strftime(config.TIME_FORMAT)))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
# QUERY HELPERS — used by Flask routes
# ══════════════════════════════════════════════════════════════

def get_all_sessions(mode):
    """Returns all sessions for a mode, newest first."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, mode, subject, date, start_time, end_time,
               total_photos, status
        FROM sessions
        ORDER BY date DESC, start_time DESC
    """)

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_session_attendance(mode, session_id):
    """Returns attendance records for a specific session including student name."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.student_id, a.name, a.photos_detected, a.status,
               s.total_photos, s.subject, s.date, s.start_time
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        WHERE a.session_id = ?
        ORDER BY a.student_id
    """, (session_id,))

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_student_history(mode, student_id):
    """Returns all session attendance records for a specific student."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.date, s.subject, s.start_time, s.total_photos,
               a.photos_detected, a.status, a.session_id
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        WHERE a.student_id = ?
        ORDER BY s.date DESC, s.start_time DESC
    """, (str(student_id),))

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_student_stats(mode, student_id):
    """
    Returns summary stats for a student in a given mode.
    Returns dict: { total, present, absent, percentage }
    """
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present
        FROM attendance
        WHERE student_id = ?
    """, (str(student_id),))

    row     = cursor.fetchone()
    conn.close()

    total   = row["total"]   if row and row["total"]   else 0
    present = row["present"] if row and row["present"] else 0
    absent  = total - present
    pct     = round((present / total) * 100, 1) if total > 0 else 0.0

    return {
        "total"      : total,
        "present"    : present,
        "absent"     : absent,
        "percentage" : pct
    }


# ══════════════════════════════════════════════════════════════
# CALENDAR & DATE HELPERS — used by /attendance page
# ══════════════════════════════════════════════════════════════

def get_attendance_by_date(date_str):
    """
    Returns attendance for all three modes on a given date.
    date_str: 'YYYY-MM-DD'
    Returns dict: { mode: [ {student_id, name, status, photos_detected, subject, start_time} ] }
    """
    result = {}

    for mode in ("demo", "upload", "lecture"):
        conn   = get_db(mode)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.student_id, a.name, a.photos_detected, a.status,
                   s.subject, s.start_time
            FROM attendance a
            JOIN sessions s ON s.id = a.session_id
            WHERE s.date = ?
            ORDER BY s.start_time, a.student_id
        """, (date_str,))

        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        result[mode] = rows

    return result


def get_calendar_data(student_id, mode):
    """
    Returns a dict of { 'YYYY-MM-DD': 'Present'|'Absent' }
    for a student in a given mode.
    If multiple sessions on same date, Present wins.
    """
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.date, a.status
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        WHERE a.student_id = ?
        ORDER BY s.date DESC
    """, (str(student_id),))

    rows   = cursor.fetchall()
    conn.close()

    result = {}
    for row in rows:
        date   = row["date"]
        status = row["status"]
        if date not in result or status == "Present":
            result[date] = status

    return result


def get_date_detail(student_id, date_str, mode):
    """Returns all session records for a student on a specific date and mode."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.subject, s.start_time, s.total_photos,
               a.photos_detected, a.status
        FROM attendance a
        JOIN sessions s ON s.id = a.session_id
        WHERE a.student_id = ? AND s.date = ?
        ORDER BY s.start_time
    """, (str(student_id), date_str))

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]