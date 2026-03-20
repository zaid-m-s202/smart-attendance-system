import os

# ── Base Directory ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Paths ──────────────────────────────────────────────────────
KNOWN_FACES_DIR    = os.path.join(BASE_DIR, "student_faces")
ENCODINGS_PATH     = os.path.join(BASE_DIR, "models", "encodings.pkl")
ATTENDANCE_LOG_DIR = os.path.join(BASE_DIR, "attendance_logs")
STUDENTS_CSV       = os.path.join(BASE_DIR, "data", "students.csv")
UPLOAD_SCAN_FOLDER = os.path.join(BASE_DIR, "upload_scan")

# ── Camera Source ──────────────────────────────────────────────
CAMERA_INDEX       = 1  # 0 = built-in laptop cam, 1 = USB webcam

# ── Recognition Settings ───────────────────────────────────────
TOLERANCE          = 0.45
MIN_FACE_DISTANCE  = 0.45
FRAME_THICKNESS    = 2
FONT_SCALE         = 0.7
MODEL              = "hog"  # hog = CPU, cnn = GPU

# ── Frame Processing ───────────────────────────────────────────
RESIZE_SCALE       = 0.5
PROCESS_EVERY_N    = 1

# ── Attendance Settings ────────────────────────────────────────
DATE_FORMAT         = "%Y-%m-%d"
TIME_FORMAT         = "%H:%M:%S"
SHOW_CONFIDENCE     = True
CSV_RETENTION_HOURS = 12
PRESENT_THRESHOLD   = 3

# ── Demo Mode ──────────────────────────────────────────────────
DEMO_PHOTO_COUNT    = 5
DEMO_INTERVAL_SECS  = 4
DEMO_THRESHOLD      = 3

# ── Burst Capture ──────────────────────────────────────────────
BURST_PHOTO_COUNT   = 3
BURST_INTERVAL_SECS = 5
BURST_THRESHOLD     = 3

# ── Lecture Mode ───────────────────────────────────────────────
LECTURE_PHOTO_COUNT   = 5
LECTURE_DURATION_MINS = 55
LECTURE_FIRST_OFFSET  = 2.5
LECTURE_LAST_OFFSET   = 1.5
LECTURE_THRESHOLD     = 3

# ── Upload Mode ────────────────────────────────────────────────
UPLOAD_THRESHOLD  = 3   # Must appear in 3 of 5 to be Present
UPLOAD_PHOTO_MAX  = 5   # Max photos per upload session