import os

# ── Base Directory ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Paths ──────────────────────────────────────────────────────
KNOWN_FACES_DIR    = os.path.join(BASE_DIR, "student_faces")
ENCODINGS_PATH     = os.path.join(BASE_DIR, "models", "encodings.pkl")
ATTENDANCE_LOG_DIR = os.path.join(BASE_DIR, "attendance_logs")
STUDENTS_CSV       = os.path.join(BASE_DIR, "data", "students.csv")

# ── Recognition Settings ───────────────────────────────────────
TOLERANCE          = 0.45  # Stricter than before — reduces false matches
MIN_FACE_DISTANCE  = 0.45  # Face must be THIS confident to be accepted
FRAME_THICKNESS    = 2
FONT_SCALE         = 0.7
MODEL              = "hog"  # hog = CPU, cnn = GPU (more accurate but slower)

# ── Frame Processing ───────────────────────────────────────────
RESIZE_SCALE       = 0.5   # Was 0.25 — now 0.5 for better face detection
PROCESS_EVERY_N    = 1     # Process every frame (we compensate via resize)

# ── Attendance Settings ────────────────────────────────────────
DATE_FORMAT        = "%Y-%m-%d"
TIME_FORMAT        = "%H:%M:%S"

# ── Confidence Display ─────────────────────────────────────────
SHOW_CONFIDENCE    = True  # Show match % on screen for debugging