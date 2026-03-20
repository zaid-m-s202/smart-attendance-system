import cv2
import os
import sys
import pickle

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def draw_face_box(frame, top, right, bottom, left, name, is_known):
    """
    Draws a bounding box and name label around a detected face.
    Green box = known student, Red box = unknown person.
    """
    color = (0, 255, 0) if is_known else (0, 0, 255)

    cv2.rectangle(frame, (left, top), (right, bottom), color, config.FRAME_THICKNESS)
    cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
    cv2.putText(
        frame,
        name,
        (left + 6, bottom - 8),
        cv2.FONT_HERSHEY_DUPLEX,
        config.FONT_SCALE,
        (255, 255, 255),
        1
    )
    return frame


def draw_status_bar(frame, marked_today):
    """Draws a status bar at the top of the frame."""
    text = f"Marked Present Today: {len(marked_today)}"
    cv2.putText(
        frame,
        text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )
    return frame


def load_encodings(encodings_path):
    """
    Loads face encodings from disk.
    Returns None if file doesn't exist or is malformed.
    """
    if not os.path.exists(encodings_path):
        print(f"[ERROR] Encodings file not found at: {encodings_path}")
        print("        Please run encode_faces.py first.")
        return None

    with open(encodings_path, "rb") as f:
        data = pickle.load(f)

    if not all(k in data for k in ("encodings", "names", "ids")):
        print("[ERROR] encodings.pkl is malformed — please re-run encode_faces.py")
        return None

    print(f"[OK] Loaded {len(data['encodings'])} encoding(s) from disk")
    return data