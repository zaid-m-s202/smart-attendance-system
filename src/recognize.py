import face_recognition
import cv2
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.utils import draw_face_box, draw_status_bar, load_encodings
from src.attendance import mark_attendance

def run_recognition():
    print("\n[STARTING] Smart Attendance System")
    print("Press 'Q' to quit\n")

    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        return

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    print(f"[OK] Opening camera (index {config.CAMERA_INDEX})...")
    cap = cv2.VideoCapture(config.CAMERA_INDEX)

    if not cap.isOpened():
        print("[ERROR] Could not open camera. Check if it is connected.")
        return

    print("[OK] Camera opened successfully")
    print("[RUNNING] Recognition active — show face to camera\n")

    marked_today       = set()
    process_this_frame = True

    # ── Initialise before loop to avoid UnboundLocalError ──────
    face_locations = []
    face_names     = []
    face_ids       = []
    face_known     = []

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("[ERROR] Failed to read frame from camera.")
                break

            if process_this_frame:
                small_frame     = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                face_locations = face_recognition.face_locations(
                    rgb_small_frame, model=config.MODEL
                )
                face_encodings = face_recognition.face_encodings(
                    rgb_small_frame, face_locations
                )

                face_names = []
                face_ids   = []
                face_known = []

                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(
                        known_encodings, face_encoding, tolerance=config.TOLERANCE
                    )
                    face_distances = face_recognition.face_distance(
                        known_encodings, face_encoding
                    )

                    name       = "Unknown"
                    student_id = None
                    is_known   = False

                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)

                        if matches[best_match_index]:
                            name       = known_names[best_match_index]
                            student_id = known_ids[best_match_index]
                            is_known   = True

                            if name not in marked_today:
                                success = mark_attendance(student_id, name)
                                if success:
                                    marked_today.add(name)

                    face_names.append(name)
                    face_ids.append(student_id)
                    face_known.append(is_known)

            process_this_frame = not process_this_frame

            for (top, right, bottom, left), name, is_known in zip(
                face_locations, face_names, face_known
            ):
                top    *= 4
                right  *= 4
                bottom *= 4
                left   *= 4
                frame = draw_face_box(frame, top, right, bottom, left, name, is_known)

            frame = draw_status_bar(frame, marked_today)
            cv2.imshow("Smart Attendance System", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("\n[EXIT] Shutting down...")
                break

    except KeyboardInterrupt:
        print("\n[EXIT] Interrupted by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"\n[DONE] Session complete.")
        print(f"[DONE] Marked present this session: {marked_today if marked_today else 'None'}")

if __name__ == "__main__":
    run_recognition()