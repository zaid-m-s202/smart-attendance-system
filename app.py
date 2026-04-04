from flask import Flask, render_template, jsonify, request, send_file
import os
import sys
import threading
import time
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.database import (
    initialize_all_databases,
    create_session, close_session, log_photo_detection,
    get_all_sessions, get_session_attendance,
    get_student_history, get_student_stats
)
from src.attendance import mark_attendance, get_today_log_path, get_today_present
from src.schedule import (
    get_current_lecture, get_next_lecture, get_current_break,
    get_full_schedule, get_lecture_photo_times, format_time
)
from src.utils import load_encodings

app = Flask(__name__)

# ── Initialize all three databases on startup ──────────────────
initialize_all_databases()

# ── Global session state ───────────────────────────────────────
session_state = {
    "running"     : False,
    "mode"        : None,
    "status"      : "idle",
    "log"         : [],
    "session_id"  : None,
    "photo_count" : 0,
}


def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    session_state["log"].append(f"[{timestamp}] {message}")
    print(message)


def run_recognition_on_frame(frame, data):
    import face_recognition
    import cv2
    import numpy as np

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    rgb       = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model=config.MODEL)
    encodings = face_recognition.face_encodings(rgb, locations)

    detected = {}
    for encoding in encodings:
        distances = face_recognition.face_distance(known_encodings, encoding)
        matches   = face_recognition.compare_faces(
            known_encodings, encoding, tolerance=config.TOLERANCE
        )
        if len(distances) == 0:
            continue
        best_idx  = int(distances.argmin())
        best_dist = distances[best_idx]
        if matches[best_idx] and best_dist < config.MIN_FACE_DISTANCE:
            name       = known_names[best_idx]
            student_id = known_ids[best_idx]
            confidence = round((1 - best_dist) * 100, 1)
            detected[name] = {"id": student_id, "confidence": confidence}

    return detected


def capture_single_photo():
    import cv2
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


# ══════════════════════════════════════════════════════════════
# DEMO MODE — writes to demo.db
# ══════════════════════════════════════════════════════════════
def run_demo_mode():
    session_state.update({
        "running": True, "mode": "demo",
        "status": "running", "log": [], "photo_count": 0
    })
    add_log("Demo mode started — 5 photos in 20 seconds")

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        add_log("ERROR: Could not load encodings")
        session_state.update({"running": False, "status": "error"})
        return

    session_id = create_session("demo")
    session_state["session_id"] = session_id
    detection_counts = defaultdict(int)

    for photo_num in range(1, config.DEMO_PHOTO_COUNT + 1):
        add_log(f"Capturing photo {photo_num} of {config.DEMO_PHOTO_COUNT}...")
        frame = capture_single_photo()

        if frame is None:
            add_log(f"ERROR: Could not capture photo {photo_num}")
        else:
            session_state["photo_count"] = photo_num
            detected = run_recognition_on_frame(frame, data)
            if detected:
                for name, info in detected.items():
                    detection_counts[name] += 1
                    log_photo_detection("demo", session_id, photo_num,
                                        str(info["id"]), info["confidence"])
                    add_log(f"Detected: {name} ({info['confidence']}%)")
            else:
                add_log(f"No known faces in photo {photo_num}")

        if photo_num < config.DEMO_PHOTO_COUNT:
            add_log(f"Next photo in {config.DEMO_INTERVAL_SECS}s...")
            time.sleep(config.DEMO_INTERVAL_SECS)

    add_log("Processing attendance...")
    students_df = pd.read_csv(config.STUDENTS_CSV)
    close_session("demo", session_id, config.DEMO_PHOTO_COUNT,
                  students_df, detection_counts)

    present, absent = [], []
    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)
        if count >= config.DEMO_THRESHOLD:
            mark_attendance(student_id, name, mode="demo")
            present.append(name)
            add_log(f"PRESENT: {name} ({count}/{config.DEMO_PHOTO_COUNT} photos)")
        else:
            absent.append(name)
            add_log(f"ABSENT: {name} ({count}/{config.DEMO_PHOTO_COUNT} photos)")

    add_log(f"Done — Present: {len(present)}, Absent: {len(absent)}")
    session_state.update({"running": False, "status": "complete"})


# ══════════════════════════════════════════════════════════════
# LECTURE MODE — writes to lecture.db, 5 photos over 55 mins
# ══════════════════════════════════════════════════════════════
def run_lecture_mode():
    session_state.update({
        "running": True, "mode": "lecture",
        "status": "running", "log": [], "photo_count": 0
    })

    lecture = get_current_lecture()
    if not lecture:
        add_log("ERROR: No lecture active right now")
        session_state.update({"running": False, "status": "error"})
        return

    subject     = lecture["subject"]
    photo_times = get_lecture_photo_times(lecture)

    add_log(f"Lecture mode started — Subject: {subject}")
    add_log(f"Schedule: {format_time(lecture['start'])} → {format_time(lecture['end'])}")
    add_log(f"5 photos planned:")
    for i, t in enumerate(photo_times, 1):
        add_log(f"  Photo {i} → {t.strftime('%H:%M:%S')}")

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        add_log("ERROR: Could not load encodings")
        session_state.update({"running": False, "status": "error"})
        return

    session_id = create_session("lecture", subject=subject)
    session_state["session_id"] = session_id
    detection_counts = defaultdict(int)

    try:
        for photo_num, photo_time in enumerate(photo_times, 1):
            now = datetime.now()
            if photo_time > now:
                wait_secs = (photo_time - now).total_seconds()
                add_log(f"Waiting {int(wait_secs)}s for photo {photo_num}...")
                time.sleep(wait_secs)

            add_log(f"Capturing photo {photo_num} of 5...")
            frame = capture_single_photo()
            session_state["photo_count"] = photo_num

            if frame is None:
                add_log(f"ERROR: Could not capture photo {photo_num}")
                continue

            detected = run_recognition_on_frame(frame, data)
            if detected:
                for name, info in detected.items():
                    detection_counts[name] += 1
                    log_photo_detection("lecture", session_id, photo_num,
                                        str(info["id"]), info["confidence"])
                    add_log(f"Detected: {name} ({info['confidence']}%)")
            else:
                add_log(f"No known faces in photo {photo_num}")

            if photo_num < 5:
                next_t = photo_times[photo_num]
                add_log(f"Next photo at {next_t.strftime('%H:%M:%S')}")

    except Exception as e:
        add_log(f"ERROR during lecture: {e}")

    # Finalize
    add_log("Finalizing attendance...")
    students_df = pd.read_csv(config.STUDENTS_CSV)
    close_session("lecture", session_id, 5, students_df, detection_counts)

    present, absent = [], []
    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)
        if count >= config.LECTURE_THRESHOLD:
            mark_attendance(student_id, name, mode="lecture")
            present.append(name)
            add_log(f"PRESENT: {name} ({count}/5 photos)")
        else:
            absent.append(name)
            add_log(f"ABSENT: {name} ({count}/5 photos)")

    add_log(f"Lecture complete — Present: {len(present)}, Absent: {len(absent)}")
    session_state.update({"running": False, "status": "complete"})


# ══════════════════════════════════════════════════════════════
# UPLOAD MODE — writes to upload.db
# ══════════════════════════════════════════════════════════════
def process_upload_session(files):
    import face_recognition
    import cv2
    import numpy as np

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        return None, None

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    session_id       = create_session("upload")
    detection_counts = defaultdict(int)
    photo_results    = []

    for i, file in enumerate(files, 1):
        file_bytes = file.read()
        np_arr     = np.frombuffer(file_bytes, np.uint8)
        image      = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            photo_results.append({
                "photo": i, "filename": file.filename,
                "detected": [], "error": "Could not read image"
            })
            continue

        rgb       = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model=config.MODEL)
        encodings = face_recognition.face_encodings(rgb, locations)

        detected_in_photo = []
        detected_names_this_photo = set()  # prevent double-counting in same photo
        for encoding in encodings:
            distances = face_recognition.face_distance(known_encodings, encoding)
            matches   = face_recognition.compare_faces(
                known_encodings, encoding, tolerance=config.TOLERANCE
            )
            if len(distances) == 0:
                continue
            best_idx  = int(np.argmin(distances))
            best_dist = distances[best_idx]
            if matches[best_idx] and best_dist < config.MIN_FACE_DISTANCE:
                name       = known_names[best_idx]
                student_id = known_ids[best_idx]
                confidence = round((1 - best_dist) * 100, 1)
                if name not in detected_names_this_photo:   # only count once per photo
                    detected_names_this_photo.add(name)
                    detection_counts[name] += 1
                    log_photo_detection("upload", session_id, i,
                                        str(student_id), confidence)
                detected_in_photo.append({"name": name, "confidence": confidence})

        photo_results.append({
            "photo": i, "filename": file.filename,
            "detected": detected_in_photo, "error": None
        })

    students_df  = pd.read_csv(config.STUDENTS_CSV)
    total_photos = len(files)
    close_session("upload", session_id, total_photos, students_df, detection_counts)

    attendance = []
    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)
        status     = "Present" if count >= config.UPLOAD_THRESHOLD else "Absent"
        if status == "Present":
            mark_attendance(student_id, name, mode="upload")
        attendance.append({
            "student_id": student_id, "name": name,
            "photos_detected": count, "total_photos": total_photos,
            "status": status
        })

    return photo_results, attendance


# ══════════════════════════════════════════════════════════════
# ATTENDANCE CALENDAR DATA — used by /attendance page
# ══════════════════════════════════════════════════════════════
def get_attendance_by_date(date_str):
    """
    Returns attendance for all three modes on a given date.
    date_str: 'YYYY-MM-DD'
    Returns dict: { mode: [ {student_id, student_name, status, photos_detected} ] }
    """
    from src.database import get_db
    result = {}

    for mode in ("demo", "upload", "lecture"):
        conn   = get_db(mode)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.student_id, a.photos_detected, a.status,
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
    for the last 30 days for a student in a given mode.
    """
    from src.database import get_db
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

    # If multiple sessions on same date, Present wins
    result = {}
    for row in rows:
        date   = row["date"]
        status = row["status"]
        if date not in result or status == "Present":
            result[date] = status

    return result


def get_date_detail(student_id, date_str, mode):
    """Returns all session records for a student on a specific date and mode."""
    from src.database import get_db
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


# ══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    current_lecture = get_current_lecture()
    next_lecture    = get_next_lecture()
    current_break   = get_current_break()
    full_schedule   = get_full_schedule()

    log_path      = get_today_log_path()
    present_count = 0
    total_count   = 0

    try:
        students_df   = pd.read_csv(config.STUDENTS_CSV)
        total_count   = len(students_df)
        if os.path.exists(log_path):
            att_df        = pd.read_csv(log_path)
            present_count = att_df["name"].nunique()
    except Exception:
        pass

    return render_template("index.html",
        current_lecture = current_lecture,
        next_lecture    = next_lecture,
        current_break   = current_break,
        full_schedule   = full_schedule,
        present_count   = present_count,
        total_count     = total_count,
        absent_count    = total_count - present_count,
        session_state   = session_state,
        format_time     = format_time
    )


@app.route("/start_demo", methods=["POST"])
def start_demo():
    if session_state["running"]:
        return jsonify({"error": "A session is already running"}), 400
    threading.Thread(target=run_demo_mode, daemon=True).start()
    return jsonify({"status": "started", "mode": "demo"})


@app.route("/start_lecture", methods=["POST"])
def start_lecture():
    if session_state["running"]:
        return jsonify({"error": "A session is already running"}), 400
    lecture = get_current_lecture()
    if not lecture:
        return jsonify({"error": "No lecture active right now. Check the schedule."}), 400
    threading.Thread(target=run_lecture_mode, daemon=True).start()
    return jsonify({"status": "started", "mode": "lecture", "subject": lecture["subject"]})


@app.route("/session_status")
def session_status():
    return jsonify({
        "running"     : session_state["running"],
        "mode"        : session_state["mode"],
        "status"      : session_state["status"],
        "log"         : session_state["log"][-20:],
        "photo_count" : session_state["photo_count"]
    })


@app.route("/today")
def today():
    records = []
    try:
        students_df    = pd.read_csv(config.STUDENTS_CSV)
        demo_present   = get_today_present(mode="demo")
        upload_present = get_today_present(mode="upload")
        lecture_present = get_today_present(mode="lecture")

        for _, student in students_df.iterrows():
            name = student["name"]
            records.append({
                "student_id"      : student["student_id"],
                "name"            : name,
                "demo_status"     : "Present" if name in demo_present    else "Absent",
                "upload_status"   : "Present" if name in upload_present  else "Absent",
                "lecture_status"  : "Present" if name in lecture_present else "Absent",
            })
    except Exception as e:
        print(f"Error loading today: {e}")

    return render_template("today.html",
        records                = records,
        demo_present_count     = sum(1 for r in records if r["demo_status"]    == "Present"),
        upload_present_count   = sum(1 for r in records if r["upload_status"]  == "Present"),
        lecture_present_count  = sum(1 for r in records if r["lecture_status"] == "Present"),
        total_count            = len(records),
        date                   = datetime.now().strftime("%B %d, %Y")
    )


@app.route("/sessions/<mode>")
def sessions(mode):
    if mode not in ("demo", "upload", "lecture"):
        return "Invalid mode", 404
    all_sessions = get_all_sessions(mode)
    return render_template("sessions.html", sessions=all_sessions, mode=mode)


@app.route("/session/<mode>/<int:session_id>")
def session_detail(mode, session_id):
    if mode not in ("demo", "upload", "lecture"):
        return "Invalid mode", 404
    records      = get_session_attendance(mode, session_id)
    all_sessions = get_all_sessions(mode)
    selected     = next((s for s in all_sessions if s["id"] == session_id), None)
    present      = sum(1 for r in records if r["status"] == "Present")
    return render_template("sessions.html",
        sessions      = all_sessions,
        mode          = mode,
        selected      = selected,
        records       = records,
        present_count = present,
        absent_count  = len(records) - present,
        total_count   = len(records)
    )


@app.route("/students")
def students():
    try:
        students_df  = pd.read_csv(config.STUDENTS_CSV)
        student_list = students_df.to_dict("records")
    except Exception:
        student_list = []
    return render_template("student.html", students=student_list)


@app.route("/student/<student_id>")
def student_detail(student_id):
    try:
        students_df = pd.read_csv(config.STUDENTS_CSV)
        row         = students_df[students_df["student_id"] == int(student_id)]
        name        = row.iloc[0]["name"] if not row.empty else student_id
        student_list = students_df.to_dict("records")
    except Exception:
        name         = student_id
        student_list = []

    demo_records    = get_student_history("demo",    student_id)
    upload_records  = get_student_history("upload",  student_id)
    lecture_records = get_student_history("lecture", student_id)
    demo_stats      = get_student_stats("demo",      student_id)
    upload_stats    = get_student_stats("upload",    student_id)
    lecture_stats   = get_student_stats("lecture",   student_id)

    return render_template("student.html",
        students        = student_list,
        selected_id     = student_id,
        name            = name,
        demo_records    = demo_records,
        upload_records  = upload_records,
        lecture_records = lecture_records,
        demo_stats      = demo_stats,
        upload_stats    = upload_stats,
        lecture_stats   = lecture_stats,
    )


# ── Attendance Calendar Routes ─────────────────────────────────

@app.route("/attendance")
def attendance():
    try:
        students_df  = pd.read_csv(config.STUDENTS_CSV)
        student_list = students_df.to_dict("records")
    except Exception:
        student_list = []
    return render_template("attendance.html", students=student_list)


@app.route("/api/attendance/by_date/<date_str>")
def api_attendance_by_date(date_str):
    data = get_attendance_by_date(date_str)
    return jsonify(data)


@app.route("/api/attendance/calendar/<mode>/<student_id>")
def api_calendar(mode, student_id):
    if mode not in ("demo", "upload", "lecture"):
        return jsonify({"error": "Invalid mode"}), 400
    data = get_calendar_data(student_id, mode)
    return jsonify(data)


@app.route("/api/attendance/detail/<mode>/<student_id>/<date_str>")
def api_date_detail(mode, student_id, date_str):
    data = get_date_detail(student_id, date_str, mode)
    return jsonify(data)


@app.route("/upload")
def upload_page():
    return render_template("upload.html")


@app.route("/process_uploads", methods=["POST"])
def process_uploads():
    files = request.files.getlist("photos")
    if not files or len(files) == 0:
        return jsonify({"error": "No photos uploaded"}), 400
    if len(files) > config.UPLOAD_PHOTO_MAX:
        return jsonify({"error": f"Maximum {config.UPLOAD_PHOTO_MAX} photos allowed"}), 400

    photo_results, attendance = process_upload_session(files)
    if photo_results is None:
        return jsonify({"error": "Encodings not found"}), 500

    return jsonify({
        "photo_results": photo_results,
        "attendance":    attendance,
        "total_photos":  len(files),
        "present":       sum(1 for a in attendance if a["status"] == "Present"),
        "absent":        sum(1 for a in attendance if a["status"] == "Absent")
    })


@app.route("/export/today")
def export_today():
    log_path = get_today_log_path()
    if not os.path.exists(log_path):
        return "No attendance data for today", 404
    return send_file(log_path, as_attachment=True)


@app.route("/export/session/<mode>/<int:session_id>")
def export_session(mode, session_id):
    records = get_session_attendance(mode, session_id)
    df      = pd.DataFrame(records)
    path    = os.path.join(config.BASE_DIR, "temp_export.csv")
    df.to_csv(path, index=False)
    return send_file(path, as_attachment=True,
                     download_name=f"{mode}_session_{session_id}.csv")


if __name__ == "__main__":
    print("\n[STARTING] Smart Attendance Web App")
    print("[INFO] Open http://127.0.0.1:5000 in your browser\n")
    app.run(debug=True, use_reloader=False)