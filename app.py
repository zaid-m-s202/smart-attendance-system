from flask import Flask, render_template, jsonify, request, send_file
import os
import sys
import threading
import time
import pandas as pd
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.database import (
    initialize_database, sync_students_from_csv,
    create_lecture, close_lecture, log_photo_detection,
    get_lecture_attendance, get_all_lectures
)
from src.attendance import mark_attendance, get_today_log_path
from src.schedule import (
    get_current_lecture, get_next_lecture, get_current_break,
    get_lecture_photo_times, get_time_until_next_lecture,
    get_lecture_status, get_full_schedule, format_time
)
from src.utils import load_encodings

app = Flask(__name__)

# ── Initialize on startup ──────────────────────────────────────
initialize_database()
sync_students_from_csv()

# ── Global session state ───────────────────────────────────────
session_state = {
    "running"     : False,
    "mode"        : None,       # "demo" or "lecture"
    "status"      : "idle",
    "log"         : [],
    "lecture_id"  : None,
    "photo_count" : 0,
}


def add_log(message):
    """Adds a timestamped message to the session log."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    session_state["log"].append(f"[{timestamp}] {message}")
    print(message)


def run_recognition_on_frame(frame, data):
    """Runs face recognition on a single frame. Returns detected students."""
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
    """Opens webcam, captures one frame, closes webcam. Returns frame."""
    import cv2
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return None
    return frame


# ══════════════════════════════════════════════════════════════
# DEMO MODE — 5 photos in 20 seconds
# ══════════════════════════════════════════════════════════════
def run_demo_mode():
    session_state["running"]     = True
    session_state["mode"]        = "demo"
    session_state["status"]      = "running"
    session_state["log"]         = []
    session_state["photo_count"] = 0

    add_log("Demo mode started — 5 photos in 20 seconds")

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        add_log("ERROR: Could not load encodings")
        session_state["running"] = False
        session_state["status"]  = "error"
        return

    detection_counts = defaultdict(int)
    detection_ids    = {}

    interval = 4  # 5 photos × 4 seconds = 20 seconds

    for photo_num in range(1, 6):
        add_log(f"Capturing photo {photo_num} of 5...")
        frame = capture_single_photo()

        if frame is None:
            add_log(f"ERROR: Could not capture photo {photo_num}")
            continue

        session_state["photo_count"] = photo_num
        detected = run_recognition_on_frame(frame, data)

        if detected:
            for name, info in detected.items():
                detection_counts[name] += 1
                detection_ids[name]     = info["id"]
                add_log(f"Detected: {name} ({info['confidence']}%)")
        else:
            add_log(f"No known faces in photo {photo_num}")

        if photo_num < 5:
            add_log(f"Next photo in {interval} seconds...")
            time.sleep(interval)

    # ── Mark attendance ────────────────────────────────────────
    add_log("Processing attendance...")
    students_df = pd.read_csv(config.STUDENTS_CSV)

    present = []
    absent  = []

    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)

        if count >= config.LECTURE_THRESHOLD:
            mark_attendance(student_id, name)
            present.append(name)
            add_log(f"PRESENT: {name} (detected in {count}/5 photos)")
        else:
            absent.append(name)
            add_log(f"ABSENT: {name} (detected in {count}/5 photos)")

    add_log(f"Done — Present: {len(present)}, Absent: {len(absent)}")
    session_state["running"] = False
    session_state["status"]  = "complete"


# ══════════════════════════════════════════════════════════════
# REAL LECTURE MODE — 5 photos over 55 minutes
# ══════════════════════════════════════════════════════════════
def run_lecture_mode():
    session_state["running"]     = True
    session_state["mode"]        = "lecture"
    session_state["status"]      = "running"
    session_state["log"]         = []
    session_state["photo_count"] = 0

    lecture = get_current_lecture()
    if not lecture:
        add_log("ERROR: No lecture is active right now")
        session_state["running"] = False
        session_state["status"]  = "error"
        return

    add_log(f"Lecture mode started: {lecture['subject']}")
    add_log(f"Schedule: {format_time(lecture['start'])} → {format_time(lecture['end'])}")

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        add_log("ERROR: Could not load encodings")
        session_state["running"] = False
        session_state["status"]  = "error"
        return

    lecture_id       = create_lecture()
    session_state["lecture_id"] = lecture_id

    photo_times      = get_lecture_photo_times(lecture)
    detection_counts = defaultdict(int)

    add_log("Photo schedule:")
    for i, t in enumerate(photo_times, 1):
        add_log(f"  Photo {i} → {t.strftime('%H:%M:%S')}")

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
                log_photo_detection(
                    lecture_id, photo_num,
                    str(info["id"]), info["confidence"]
                )
                add_log(f"Detected: {name} ({info['confidence']}%)")
        else:
            add_log(f"No known faces in photo {photo_num}")

    # ── Final attendance ───────────────────────────────────────
    add_log("Finalizing attendance...")
    close_lecture(lecture_id, 5)

    students_df = pd.read_csv(config.STUDENTS_CSV)
    present = []
    absent  = []

    for _, student in students_df.iterrows():
        name  = student["name"]
        sid   = str(student["student_id"])
        count = detection_counts.get(name, 0)

        if count >= config.LECTURE_THRESHOLD:
            mark_attendance(sid, name)
            present.append(name)
            add_log(f"PRESENT: {name} ({count}/5 photos)")
        else:
            absent.append(name)
            add_log(f"ABSENT: {name} ({count}/5 photos)")

    add_log(f"Lecture complete — Present: {len(present)}, Absent: {len(absent)}")
    session_state["running"] = False
    session_state["status"]  = "complete"


# ══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    current_lecture = get_current_lecture()
    next_lecture    = get_next_lecture()
    current_break   = get_current_break()
    full_schedule   = get_full_schedule()

    # Today's attendance summary
    log_path = get_today_log_path()
    present_count = 0
    total_count   = 0

    try:
        students_df   = pd.read_csv(config.STUDENTS_CSV)
        total_count   = len(students_df)
        if os.path.exists(log_path):
            att_df        = pd.read_csv(log_path)
            present_count = len(att_df)
    except Exception:
        pass

    # Alert if lecture active but no attendance marked
    alert = None
    if current_lecture and present_count == 0:
        alert = f"No attendance marked yet for {current_lecture['subject']}!"

    return render_template("index.html",
        current_lecture  = current_lecture,
        next_lecture     = next_lecture,
        current_break    = current_break,
        full_schedule    = full_schedule,
        present_count    = present_count,
        total_count      = total_count,
        absent_count     = total_count - present_count,
        alert            = alert,
        session_state    = session_state,
        format_time      = format_time
    )


@app.route("/start_demo", methods=["POST"])
def start_demo():
    if session_state["running"]:
        return jsonify({"error": "A session is already running"}), 400
    thread = threading.Thread(target=run_demo_mode, daemon=True)
    thread.start()
    return jsonify({"status": "started", "mode": "demo"})


@app.route("/start_lecture", methods=["POST"])
def start_lecture():
    if session_state["running"]:
        return jsonify({"error": "A session is already running"}), 400
    lecture = get_current_lecture()
    if not lecture:
        return jsonify({"error": "No lecture is active right now"}), 400
    thread = threading.Thread(target=run_lecture_mode, daemon=True)
    thread.start()
    return jsonify({"status": "started", "mode": "lecture"})


@app.route("/session_status")
def session_status():
    return jsonify({
        "running"     : session_state["running"],
        "mode"        : session_state["mode"],
        "status"      : session_state["status"],
        "log"         : session_state["log"][-20:],  # last 20 lines
        "photo_count" : session_state["photo_count"]
    })


@app.route("/today")
def today():
    log_path = get_today_log_path()
    records  = []

    try:
        students_df = pd.read_csv(config.STUDENTS_CSV)
        if os.path.exists(log_path):
            att_df  = pd.read_csv(log_path)
            marked  = set(att_df["name"].values)
        else:
            marked  = set()

        for _, student in students_df.iterrows():
            status = "Present" if student["name"] in marked else "Absent"
            time_marked = ""
            if status == "Present" and os.path.exists(log_path):
                att_df     = pd.read_csv(log_path)
                row        = att_df[att_df["name"] == student["name"]]
                if not row.empty:
                    time_marked = row.iloc[0]["time"]

            records.append({
                "student_id" : student["student_id"],
                "name"       : student["name"],
                "status"     : status,
                "time"       : time_marked
            })
    except Exception as e:
        print(f"Error loading today: {e}")

    present = sum(1 for r in records if r["status"] == "Present")
    return render_template("today.html",
        records       = records,
        present_count = present,
        absent_count  = len(records) - present,
        total_count   = len(records),
        date          = datetime.now().strftime("%B %d, %Y")
    )


@app.route("/lectures")
def lectures():
    all_lectures = get_all_lectures()
    return render_template("lecture.html", lectures=all_lectures)


@app.route("/lecture/<int:lecture_id>")
def lecture_detail(lecture_id):
    records  = get_lecture_attendance(lecture_id)
    lectures = get_all_lectures()
    lecture  = next((l for l in lectures if l["id"] == lecture_id), None)
    present  = sum(1 for r in records if r["status"] == "Present")

    return render_template("lecture.html",
        lectures      = lectures,
        selected      = lecture,
        records       = records,
        present_count = present,
        absent_count  = len(records) - present,
        total_count   = len(records)
    )


@app.route("/students")
def students():
    try:
        students_df = pd.read_csv(config.STUDENTS_CSV)
        student_list = students_df.to_dict("records")
    except Exception:
        student_list = []
    return render_template("student.html", students=student_list)


@app.route("/student/<student_id>")
def student_detail(student_id):
    from src.database import get_connection
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.subject, l.date, l.start_time,
               a.photos_detected, a.status
        FROM attendance a
        JOIN lectures l ON l.id = a.lecture_id
        WHERE a.student_id = ?
        ORDER BY l.date DESC, l.start_time DESC
    """, (student_id,))

    rows    = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total   = len(rows)
    present = sum(1 for r in rows if r["status"] == "Present")
    percentage = round((present / total * 100), 1) if total > 0 else 0

    try:
        students_df = pd.read_csv(config.STUDENTS_CSV)
        student     = students_df[students_df["student_id"] == int(student_id)].iloc[0]
        name        = student["name"]
    except Exception:
        name = student_id

    return render_template("student.html",
        students   = pd.read_csv(config.STUDENTS_CSV).to_dict("records"),
        selected_id = student_id,
        name        = name,
        records     = rows,
        total       = total,
        present     = present,
        absent      = total - present,
        percentage  = percentage
    )


@app.route("/export/today")
def export_today():
    log_path = get_today_log_path()
    if not os.path.exists(log_path):
        return "No attendance data for today", 404
    return send_file(log_path, as_attachment=True)


@app.route("/export/lecture/<int:lecture_id>")
def export_lecture(lecture_id):
    records  = get_lecture_attendance(lecture_id)
    df       = pd.DataFrame(records)
    path     = os.path.join(config.BASE_DIR, "temp_export.csv")
    df.to_csv(path, index=False)
    return send_file(path, as_attachment=True,
                     download_name=f"lecture_{lecture_id}_attendance.csv")

@app.route("/upload")
def upload_page():
    return render_template("upload.html")


@app.route("/process_uploads", methods=["POST"])
def process_uploads():
    import face_recognition
    import cv2
    import numpy as np

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        return jsonify({"error": "Encodings not found"}), 500

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    files = request.files.getlist("photos")

    if not files or len(files) == 0:
        return jsonify({"error": "No photos uploaded"}), 400

    if len(files) > 5:
        return jsonify({"error": "Maximum 5 photos allowed"}), 400

    detection_counts = defaultdict(int)
    detection_ids    = {}
    photo_results    = []

    for i, file in enumerate(files, 1):
        if file.filename == "":
            continue

        # Read image directly from upload
        file_bytes = file.read()
        np_arr     = np.frombuffer(file_bytes, np.uint8)
        image      = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            photo_results.append({
                "photo"    : i,
                "filename" : file.filename,
                "detected" : [],
                "error"    : "Could not read image"
            })
            continue

        rgb       = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model=config.MODEL)
        encodings = face_recognition.face_encodings(rgb, locations)

        detected_in_photo = []

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

                detection_counts[name] += 1
                detection_ids[name]     = student_id
                detected_in_photo.append({
                    "name"       : name,
                    "confidence" : confidence
                })

        photo_results.append({
            "photo"    : i,
            "filename" : file.filename,
            "detected" : detected_in_photo,
            "error"    : None
        })

    # ── Final attendance decision ───────────────────────────────
    import pandas as pd
    students_df  = pd.read_csv(config.STUDENTS_CSV)
    total_photos = len(files)
    attendance   = []

    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)
        status     = "Present" if count >= config.LECTURE_THRESHOLD else "Absent"

        if status == "Present":
            mark_attendance(student_id, name)

        attendance.append({
            "student_id"      : student_id,
            "name"            : name,
            "photos_detected" : count,
            "total_photos"    : total_photos,
            "status"          : status
        })

    return jsonify({
        "photo_results" : photo_results,
        "attendance"    : attendance,
        "total_photos"  : total_photos,
        "present"       : sum(1 for a in attendance if a["status"] == "Present"),
        "absent"        : sum(1 for a in attendance if a["status"] == "Absent")
    })

if __name__ == "__main__":
    print("\n[STARTING] Smart Attendance Web App")
    print("[INFO] Open http://127.0.0.1:5000 in your browser\n")
    app.run(debug=True, use_reloader=False)