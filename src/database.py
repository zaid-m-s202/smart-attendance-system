import sqlite3
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


DB_PATHS = {
    "demo"    : os.path.join(config.BASE_DIR, "data", "demo.db"),
    "lecture" : os.path.join(config.BASE_DIR, "data", "lecture.db"),
    "upload"  : os.path.join(config.BASE_DIR, "data", "upload.db"),
}


def get_db(mode):
    """Returns a sqlite3 connection for the given mode."""
    if mode not in DB_PATHS:
        raise ValueError(f"[DB] Invalid mode: '{mode}' — must be demo, lecture, or upload")
    path = DB_PATHS[mode]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


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


def create_session(mode, subject=None):
    """Creates a new session and returns its id."""
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
    """Closes a session and writes final attendance for every student."""
    conn   = get_db(mode)
    cursor = conn.cursor()
    now    = datetime.now()

    thresholds = {
        "demo"    : config.DEMO_THRESHOLD,
        "lecture" : config.LECTURE_THRESHOLD,
        "upload"  : config.UPLOAD_THRESHOLD,
    }
    threshold = thresholds.get(mode, 3)

    cursor.execute("""
        UPDATE sessions
        SET end_time = ?, total_photos = ?, status = 'completed'
        WHERE id = ?
    """, (now.strftime(config.TIME_FORMAT), total_photos, session_id))

    for _, student in students_df.iterrows():
        student_id = str(student["student_id"])
        name       = student["name"]
        count      = detection_counts.get(name, 0)
        status     = "Present" if count >= threshold else "Absent"

        cursor.execute("""
            INSERT INTO attendance (session_id, student_id, photos_detected, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id, session_id)
            DO UPDATE SET photos_detected = excluded.photos_detected,
                          status          = excluded.status
        """, (session_id, student_id, count, status))

    conn.commit()
    conn.close()
    print(f"[DB] Session {session_id} closed — mode={mode}")


def log_photo_detection(mode, session_id, photo_num, student_id, confidence):
    """Records a single face detection event."""
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
    """Returns attendance records for a specific session."""
    conn   = get_db(mode)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.student_id, a.photos_detected, a.status,
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
    """Returns all session attendance records for a student."""
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
    """Returns summary stats for a student in a given mode."""
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