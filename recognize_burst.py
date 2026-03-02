import face_recognition
import cv2
import numpy as np
import os
import sys
import time
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.utils import load_encodings
from src.attendance import mark_attendance


def run_burst():
    print("\n[QUICK CAPTURE] Starting in 5 seconds — get in position...")

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

    # ── Countdown with live preview ─────────────────────────────
    start_time = time.time()
    countdown  = 5

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        elapsed   = time.time() - start_time
        remaining = countdown - int(elapsed)

        if remaining <= 0:
            # Take the photo now
            capture_frame = frame.copy()
            cv2.putText(frame, "CAPTURING!", (180, 240),
                        cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 255, 0), 3)
            cv2.imshow("Quick Capture", frame)
            cv2.waitKey(800)
            break

        # Show countdown on live preview
        cv2.putText(frame, f"Photo in: {remaining}s", (180, 240),
                    cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 200, 255), 3)
        cv2.imshow("Quick Capture", frame)
        cv2.waitKey(1)

    cap.release()
    cv2.destroyAllWindows()

    # ── Run recognition on captured frame ──────────────────────
    print("\n[SCAN] Running face recognition...")

    rgb       = cv2.cvtColor(capture_frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model=config.MODEL)
    encodings = face_recognition.face_encodings(rgb, locations)

    print(f"[SCAN] Found {len(locations)} face(s) in photo\n")

    marked  = []
    unknown = 0

    for encoding in encodings:
        distances = face_recognition.face_distance(known_encodings, encoding)
        matches   = face_recognition.compare_faces(
            known_encodings, encoding, tolerance=config.TOLERANCE
        )

        if len(distances) == 0:
            continue

        best_idx  = np.argmin(distances)
        best_dist = distances[best_idx]
        name      = "Unknown"
        student_id = None

        if matches[best_idx] and best_dist < config.MIN_FACE_DISTANCE:
            name       = known_names[best_idx]
            student_id = known_ids[best_idx]
            confidence = round((1 - best_dist) * 100, 1)

        if name != "Unknown":
            success = mark_attendance(student_id, name)
            if success:
                marked.append(name)
                print(f"  [✓] Marked Present: {name} ({confidence}%)")
            else:
                print(f"  [=] Already marked today: {name}")
        else:
            unknown += 1
            print(f"  [?] Unknown face detected")

    # ── Summary ────────────────────────────────────────────────
    print(f"\n{'='*40}")
    print(f"  RESULTS")
    print(f"{'='*40}")
    print(f"  Faces detected : {len(locations)}")
    print(f"  Marked present : {len(marked)}")
    print(f"  Unknown faces  : {unknown}")
    if marked:
        print(f"  Students       : {', '.join(marked)}")
    print(f"{'='*40}\n")


if __name__ == "__main__":
    run_burst()