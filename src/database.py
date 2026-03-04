import sqlite3
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_connection():
    """Returns a connection to the SQLite database."""
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """
    Creates all tables if they don't exist.
    Safe to run multiple times — won't overwrite existing data.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Students Table ─────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            folder_name TEXT NOT NULL,
            class       TEXT
        )
    """)

    # ── Lectures Table ─────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lectures (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            subject      TEXT NOT NULL,
            date         TEXT NOT NULL,
            start_time   TEXT NOT NULL,
            end_time     TEXT,
            total_photos INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'ongoing'
        )
    """)

    # ── Attendance Table ───────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT NOT NULL,
            lecture_id      INTEGER NOT NULL,
            photos_detected INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'Absent',
            FOREIGN KEY (lecture_id) REFERENCES lectures(id),
            UNIQUE(student_id, lecture_id)
        )
    """)

    # ── Photo Log Table ────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lecture_id  INTEGER NOT NULL,
            photo_num   INTEGER NOT NULL,
            student_id  TEXT NOT NULL,
            confidence  REAL,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (lecture_id) REFERENCES lectures(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully")


def sync_students_from_csv():
    """
    Reads students.csv and inserts any new students into the database.
    Safe to run multiple times — skips existing students.
    """
    import pandas as pd

    if not os.path.exists(config.STUDENTS_CSV):
        print("[DB] students.csv not found")
        return

    df = pd.read_csv(config.STUDENTS_CSV)
    conn = get_connection()
    cursor = conn.cursor()

    added = 0
    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO students
                (student_id, name, folder_name, class)
                VALUES (?, ?, ?, ?)
            """, (
                str(row["student_id"]),
                row["name"],
                row["folder_name"],
                row.get("class", "")
            ))
            if cursor.rowcount > 0:
                added += 1
        except Exception as e:
            print(f"[DB] Error inserting student {row['name']}: {e}")

    conn.commit()
    conn.close()
    print(f"[DB] Students synced — {added} new student(s) added")


def create_lecture():
    """
    Creates a new lecture session for today.
    Returns the lecture_id to use for this session.
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    cursor.execute("""
        INSERT INTO lectures (subject, date, start_time, status)
        VALUES (?, ?, ?, 'ongoing')
    """, (
        config.SUBJECT_NAME,
        now.strftime(config.DATE_FORMAT),
        now.strftime(config.TIME_FORMAT)
    ))

    lecture_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"[DB] New lecture created — ID: {lecture_id} | Subject: {config.SUBJECT_NAME}")
    return lecture_id


def close_lecture(lecture_id, total_photos):
    """
    Closes a lecture session and finalizes attendance.
    Marks anyone with photos_detected < PRESENT_THRESHOLD as Absent.
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()

    cursor.execute("""
        UPDATE lectures
        SET end_time = ?, total_photos = ?, status = 'completed'
        WHERE id = ?
    """, (now.strftime(config.TIME_FORMAT), total_photos, lecture_id))

    cursor.execute("SELECT student_id FROM students")
    all_students = cursor.fetchall()

    for student in all_students:
        sid = student["student_id"]

        cursor.execute("""
            SELECT COUNT(DISTINCT photo_num) as count
            FROM photo_log
            WHERE lecture_id = ? AND student_id = ?
        """, (lecture_id, sid))

        result = cursor.fetchone()
        photos_detected = result["count"] if result else 0
        status = "Present" if photos_detected >= config.PRESENT_THRESHOLD else "Absent"

        cursor.execute("""
            INSERT INTO attendance (student_id, lecture_id, photos_detected, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id, lecture_id)
            DO UPDATE SET photos_detected = ?, status = ?
        """, (sid, lecture_id, photos_detected, status,
              photos_detected, status))

    conn.commit()
    conn.close()
    print(f"[DB] Lecture {lecture_id} closed — attendance finalized")


def log_photo_detection(lecture_id, photo_num, student_id, confidence):
    """Records that a student was detected in a specific photo."""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    cursor.execute("""
        INSERT INTO photo_log (lecture_id, photo_num, student_id, confidence, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (lecture_id, photo_num, student_id, confidence,
          now.strftime(config.TIME_FORMAT)))

    conn.commit()
    conn.close()


def get_lecture_attendance(lecture_id):
    """Returns full attendance report for a lecture."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.name, s.student_id, a.photos_detected, a.status
        FROM attendance a
        JOIN students s ON s.student_id = a.student_id
        WHERE a.lecture_id = ?
        ORDER BY s.name
    """, (lecture_id,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_lectures():
    """Returns all lecture sessions."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM lectures ORDER BY date DESC, start_time DESC
    """)

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_connection():
    """Returns a connection to the SQLite database."""
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn