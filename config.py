import os

# ── Base Directory ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ── Recognition Modes ──────────────────────────────────────────
UPLOAD_SCAN_FOLDER     = os.path.join(BASE_DIR, "upload_scan")

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
CSV_RETENTION_HOURS = 12

# Burst capture
BURST_PHOTO_COUNT      = 3       # Number of photos to take
BURST_INTERVAL_SECS    = 5       # Seconds between each photo
BURST_THRESHOLD        = 3       # Must appear in all 3 to be Present

# Lecture mode
LECTURE_PHOTO_COUNT    = 5       # Total photos per lecture
LECTURE_DURATION_MINS  = 55      # Total lecture duration in minutes
LECTURE_FIRST_OFFSET   = 2.5     # Minutes after start for first photo
LECTURE_LAST_OFFSET    = 1.5     # Minutes before end for last photo
LECTURE_THRESHOLD      = 3       # Must appear in 3 of 5 to be Present

# ── Database ───────────────────────────────────────────────────
DATABASE_PATH      = os.path.join(BASE_DIR, "database", "attendance.db")

# ── Flask Server ───────────────────────────────────────────────
FLASK_HOST         = "0.0.0.0"
FLASK_PORT         = 5000
UPLOAD_FOLDER      = os.path.join(BASE_DIR, "received_photos")

# ── Attendance Rule ────────────────────────────────────────────
TOTAL_PHOTOS       = 5
PRESENT_THRESHOLD  = 3
SUBJECT_NAME       = "Computer Science"

# ── Recognition Modes ──────────────────────────────────────────
UPLOAD_SCAN_FOLDER     = os.path.join(BASE_DIR, "upload_scan")

# Mode 3 — Burst capture
BURST_PHOTO_COUNT      = 3
BURST_INTERVAL_SECS    = 5
BURST_THRESHOLD        = 3

# Mode 4 — Lecture mode
LECTURE_PHOTO_COUNT    = 5
LECTURE_DURATION_MINS  = 55
LECTURE_FIRST_OFFSET   = 2.5
LECTURE_LAST_OFFSET    = 1.5
LECTURE_THRESHOLD      = 3

# ── Cleanup Settings ───────────────────────────────────────────
CSV_RETENTION_HOURS    = 12