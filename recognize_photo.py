import face_recognition
import cv2
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from src.utils import load_encodings
from src.attendance import mark_attendance


def scan_photo(image_path):
    """Runs face recognition on a single photo and marks attendance."""

    print(f"\n[SCAN] Scanning photo: {os.path.basename(image_path)}")

    # Load encodings
    data = load_encodings(config.ENCODINGS_PATH)
    if data is None:
        return

    known_encodings = data["encodings"]
    known_names     = data["names"]
    known_ids       = data["ids"]

    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"[ERROR] Could not read image: {image_path}")
        return

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Detect faces
    print("[SCAN] Detecting faces...")
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

        name       = "Unknown"
        student_id = None
        confidence = 0.0

        if len(distances) > 0:
            best_idx  = np.argmin(distances)
            best_dist = distances[best_idx]

            if matches[best_idx] and best_dist < config.MIN_FACE_DISTANCE:
                name       = known_names[best_idx]
                student_id = known_ids[best_idx]
                confidence = round((1 - best_dist) * 100, 1)

        if name != "Unknown":
            success = mark_attendance(student_id, name)
            if success:
                marked.append(f"{name} ({confidence}%)")
                print(f"  [✓] Marked Present: {name} — {confidence}% confidence")
            else:
                print(f"  [=] Already marked today: {name}")
        else:
            unknown += 1
            print(f"  [?] Unknown face detected")

    # ── Summary ────────────────────────────────────────────────
    print(f"\n[DONE] Scan complete")
    print(f"  Marked present : {len(marked)}")
    print(f"  Unknown faces  : {unknown}")
    if marked:
        print(f"  Students       : {', '.join(marked)}")


def scan_upload_folder():
    """
    Scans all images inside the upload_scan folder.
    Processes every image found then moves it to a processed subfolder.
    """
    folder = config.UPLOAD_SCAN_FOLDER
    os.makedirs(folder, exist_ok=True)

    # Find all images in folder
    valid_ext = (".jpg", ".jpeg", ".png")
    images = [
        f for f in os.listdir(folder)
        if f.lower().endswith(valid_ext)
    ]

    if not images:
        print(f"\n[INFO] No images found in: {folder}")
        print(f"[INFO] Place a photo inside the folder and run again")
        return

    print(f"\n[INFO] Found {len(images)} image(s) to scan")

    # Create processed subfolder
    processed_folder = os.path.join(folder, "processed")
    os.makedirs(processed_folder, exist_ok=True)

    for image_file in images:
        image_path = os.path.join(folder, image_file)
        scan_photo(image_path)

        # Move to processed folder after scanning
        processed_path = os.path.join(processed_folder, image_file)
        os.rename(image_path, processed_path)
        print(f"[MOVED] {image_file} → upload_scan/processed/")

    print(f"\n[COMPLETE] All images processed")


if __name__ == "__main__":
    scan_upload_folder()