import face_recognition
import cv2
import numpy as np
import os
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.utils import load_encodings
from src.attendance import mark_attendance


def calculate_photo_times(start_time):
    """
    Calculates exactly when each of the 5 photos should be taken.
    First photo at start + 2.5 mins
    Last photo at end - 1.5 mins
    Remaining 3 evenly distributed in between.
    """
    end_time   = start_time + timedelta(minutes=config.LECTURE_DURATION_MINS)
    first_time = start_time + timedelta(minutes=config.LECTURE_FIRST_OFFSET)
    last_time  = end_time   - timedelta(minutes=config.LECTURE_LAST_OFFSET)

    # Distribute 5 photos evenly between first and last
    total_gap = (last_time - first_time).total_seconds()
    interval  = total_gap / (config.LECTURE_PHOTO_COUNT - 1)

    photo_times = []
    for i in range(config.LECTURE_PHOTO_COUNT):
        t = first_time + timedelta(seconds=i * interval)
        photo_times.append(t)

    return photo_times


def capture_and_recognize(cap, known_encodings, known_names, known_ids, photo_num):
    """Captures a photo and returns detected students."""
    print(f"\n[LECTURE] Capturing photo {photo_num}...")

    ret, frame = cap.read()
    if not ret:
        print(f"[ERROR] Failed to capture photo {photo_num}")
        return {}

    # Show captured frame briefly
    cv2.imshow(f"Lecture Capture — Photo {photo_num}", frame)
    cv2.waitKey(1000)
    cv2.destroyAllWindows()

    rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

        best_idx  = np.argmin(distances)
        best_dist = distances[best_idx]

        if matches[best_idx] and best_dist < config.MIN_FACE_DISTANCE:
            name       = known_names[best_idx]
            student_id = known_ids[best_idx]
            confidence = round((1 - best_dist) * 100, 1)
            detected[name] = {"id": student_id, "confidence": confidence}
            print(f"  [✓] Detected: {name} ({confidence}% confidence)")

    if not detected:
        print(f"  [?] No known faces detected in photo {photo_num}")

    return detected


def run_lecture():
    print("\n[LECTURE MODE] Smart Attendance — Lecture Session")
    print("="*50)

    # ── Get lecture start time ──────────────────────────────────
    while True:
        try:
            time_input = input("\nEnter lecture start time (HH:MM, 24hr format): ").strip()
            now        = datetime.now()
            start_time = datetime.strptime(time_input, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            break
        except ValueError:
            print("[ERROR] Invalid format. Please enter time as HH:MM (e.g. 10:00)")

    # Calculate photo schedule
    photo_times = calculate_photo_times(start_time)
    end_time    = start_time + timedelta(minutes=config.LECTURE_DURATION_MINS)

    print(f"\n[SCHEDULE] Lecture: {start_time.strftime('%H:%M')} → {end_time.strftime('%H:%M')}")
    print(f"[SCHEDULE] Photo capture times:")
    for i, t in enumerate(photo_times, 1):
        print(f"  Photo {i} → {t.strftime('%H:%M:%S')}")

    # Load encodings
    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        return

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    detection_counts = defaultdict(int)
    detection_ids    = {}

    print(f"\n[WAITING] System ready — waiting for first photo time...")
    print(f"[INFO] Press Ctrl+C to cancel\n")

    try:
        for photo_num, photo_time in enumerate(photo_times, 1):
            now = datetime.now()

            # If scheduled time is in the future — wait for it
            if photo_time > now:
                wait_secs = (photo_time - now).total_seconds()
                print(f"[WAITING] Photo {photo_num} scheduled at {photo_time.strftime('%H:%M:%S')} — waiting {int(wait_secs)}s...")
                time.sleep(wait_secs)

            # Capture and recognize
            detected = capture_and_recognize(
                cap, known_encodings, known_names, known_ids, photo_num
            )

            for name, info in detected.items():
                detection_counts[name] += 1
                detection_ids[name]     = info["id"]

            remaining = config.LECTURE_PHOTO_COUNT - photo_num
            if remaining > 0:
                next_time = photo_times[photo_num]
                print(f"[INFO] {remaining} photo(s) remaining — next at {next_time.strftime('%H:%M:%S')}")

    except KeyboardInterrupt:
        print("\n[CANCELLED] Lecture mode cancelled by user")

    finally:
        cap.release()
        cv2.destroyAllWindows()

    # ── Final Attendance Decision ───────────────────────────────
    import pandas as pd

    print(f"\n{'='*50}")
    print(f"  LECTURE ATTENDANCE RESULTS")
    print(f"  Subject  : {config.SUBJECT_NAME}")
    print(f"  Date     : {datetime.now().strftime(config.DATE_FORMAT)}")
    print(f"  Photos   : {len(photo_times)} taken")
    print(f"  Threshold: {config.LECTURE_THRESHOLD} of {config.LECTURE_PHOTO_COUNT}")
    print(f"{'='*50}")

    students_df = pd.read_csv(config.STUDENTS_CSV)
    marked      = []
    absent      = []

    for _, student in students_df.iterrows():
        name       = student["name"]
        student_id = str(student["student_id"])
        count      = detection_counts.get(name, 0)

        if count >= config.LECTURE_THRESHOLD:
            success = mark_attendance(student_id, name)
            status  = "Present" if success else "Already marked"
            marked.append(name)
        else:
            status = "Absent"
            absent.append(name)

        print(f"  {name:<20} | {count}/{config.LECTURE_PHOTO_COUNT} photos | {status}")

    print(f"{'='*50}")
    print(f"  Present : {len(marked)}")
    print(f"  Absent  : {len(absent)}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_lecture()