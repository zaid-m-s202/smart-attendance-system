import face_recognition
import pickle
import os
import cv2
import pandas as pd
import sys

# Add parent directory to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def encode_known_faces():
    print("\n Starting face encoding process...")
    print(f" Looking for faces in: {config.KNOWN_FACES_DIR}")

    known_encodings = []
    known_names     = []
    known_ids       = []

    # ── Load student records from CSV ──────────────────────────
    if not os.path.exists(config.STUDENTS_CSV):
        print(f"[ERROR] students.csv not found at {config.STUDENTS_CSV}")
        return

    students_df = pd.read_csv(config.STUDENTS_CSV)
    print(f" Found {len(students_df)} student(s) in students.csv\n")

    # ── Loop through each student folder ───────────────────────
    for _, student in students_df.iterrows():
        folder_name = student["folder_name"]
        student_name = student["name"]
        student_id   = student["student_id"]

        student_folder = os.path.join(config.KNOWN_FACES_DIR, folder_name)

        if not os.path.exists(student_folder):
            print(f"[WARNING] Folder not found for {student_name}: {student_folder}")
            continue

        print(f" Processing student: {student_name} (ID: {student_id})")

        photo_files = [
            f for f in os.listdir(student_folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

        if not photo_files:
            print(f"  [WARNING] No photos found in {student_folder}")
            continue

        print(f"  Found {len(photo_files)} photo(s)")

        # ── Encode each photo ───────────────────────────────────
        success_count = 0
        for photo_file in photo_files:
            photo_path = os.path.join(student_folder, photo_file)

            # Load image and convert BGR (OpenCV) to RGB (face_recognition)
            image = cv2.imread(photo_path)
            if image is None:
                print(f"  [SKIP] Could not read: {photo_file}")
                continue

            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Detect face locations first
            face_locations = face_recognition.face_locations(
                rgb_image, model=config.MODEL
            )

            if not face_locations:
                print(f"  [SKIP] No face detected in: {photo_file}")
                continue

            # Compute encodings for detected faces
            encodings = face_recognition.face_encodings(rgb_image, face_locations)

            for encoding in encodings:
                known_encodings.append(encoding)
                known_names.append(student_name)
                known_ids.append(student_id)
                success_count += 1

            print(f"  [OK] {photo_file} — {len(encodings)} face(s) encoded")

        print(f"  Total encoded for {student_name}: {success_count} encoding(s)\n")

    # ── Save encodings to disk ──────────────────────────────────
    if not known_encodings:
        print("[ERROR] No encodings were generated. Check your photos.")
        return

    data = {
        "encodings" : known_encodings,
        "names"     : known_names,
        "ids"       : known_ids
    }

    os.makedirs(os.path.dirname(config.ENCODINGS_PATH), exist_ok=True)

    with open(config.ENCODINGS_PATH, "wb") as f:
        pickle.dump(data, f)

    print(f"[SUCCESS] Saved {len(known_encodings)} encoding(s) to:")
    print(f"          {config.ENCODINGS_PATH}\n")


if __name__ == "__main__":
    encode_known_faces()