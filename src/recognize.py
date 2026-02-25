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

    # ── Load encodings ─────────────────────────────────────────
    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        return

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    # ── Open webcam ────────────────────────────────────────────
    print("[OK] Opening webcam...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("[ERROR] Could not open webcam. Check if it is connected.")
        return

    print("[OK] Webcam opened successfully")
    print("[RUNNING] Recognition active — show face to camera\n")

    marked_today = set()  # Track who has been marked this session
    process_this_frame = True  # Process every other frame for speed
    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("[ERROR] Failed to read frame from webcam.")
                break

            # ── Process every other frame to save CPU ───────────────
            if process_this_frame:

                # Resize frame to 1/4 size for faster processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

                # Convert BGR (OpenCV) to RGB (face_recognition)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                # Detect face locations and encodings in current frame
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
                    # Compare detected face against all known encodings
                    matches = face_recognition.compare_faces(
                        known_encodings, face_encoding, tolerance=config.TOLERANCE
                    )
                    face_distances = face_recognition.face_distance(
                        known_encodings, face_encoding
                    )

                    name      = "Unknown"
                    student_id = None
                    is_known  = False

                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)

                        if matches[best_match_index]:
                            name       = known_names[best_match_index]
                            student_id = known_ids[best_match_index]
                            is_known   = True

                            # Mark attendance if not already marked
                            if name not in marked_today:
                                success = mark_attendance(student_id, name)
                                if success:
                                    marked_today.add(name)

                    face_names.append(name)
                    face_ids.append(student_id)
                    face_known.append(is_known)

            process_this_frame = not process_this_frame

            # ── Draw results on full size frame ─────────────────────
            for (top, right, bottom, left), name, is_known in zip(
                face_locations, face_names, face_known
            ):
                # Scale back up since we processed at 1/4 size
                top    *= 4
                right  *= 4
                bottom *= 4
                left   *= 4

                frame = draw_face_box(frame, top, right, bottom, left, name, is_known)

            # Draw status bar at top of frame
            frame = draw_status_bar(frame, marked_today)

            # Show the frame
            cv2.imshow("Smart Attendance System", frame)

            # Press Q to quit
            # Press Q to quit
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:  # Q or ESC
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