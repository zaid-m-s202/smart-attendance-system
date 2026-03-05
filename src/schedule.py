from datetime import datetime, time, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── College Schedule with real subject names ───────────────────
LECTURES = [
    {"id": 1, "subject": "AIC", "start": time(10, 0),  "end": time(10, 55)},
    {"id": 2, "subject": "SS",  "start": time(11, 0),  "end": time(11, 55)},
    {"id": 3, "subject": "CS",  "start": time(12, 0),  "end": time(12, 45)},
    # Lunch Break: 12:45 → 13:40
    {"id": 4, "subject": "E&I", "start": time(13, 40), "end": time(14, 35)},
    {"id": 5, "subject": "PME", "start": time(14, 40), "end": time(15, 30)},
    # Short Break: 15:30 → 15:40
    {"id": 6, "subject": "DS",  "start": time(15, 40), "end": time(16, 35)},
    {"id": 7, "subject": "PE",  "start": time(16, 40), "end": time(17, 30)},
]

BREAKS = [
    {"name": "Lunch Break", "start": time(12, 45), "end": time(13, 40)},
    {"name": "Short Break", "start": time(15, 30), "end": time(15, 40)},
]

SUBJECTS = [lec["subject"] for lec in LECTURES]


def get_current_lecture():
    now = datetime.now().time()
    for lecture in LECTURES:
        if lecture["start"] <= now <= lecture["end"]:
            return lecture
    return None


def get_next_lecture():
    now = datetime.now().time()
    for lecture in LECTURES:
        if lecture["start"] > now:
            return lecture
    return None


def get_current_break():
    now = datetime.now().time()
    for b in BREAKS:
        if b["start"] <= now <= b["end"]:
            return b
    return None


def get_lecture_photo_times(lecture):
    today      = datetime.now().date()
    start_dt   = datetime.combine(today, lecture["start"])
    end_dt     = datetime.combine(today, lecture["end"])
    first_time = start_dt + timedelta(minutes=2.5)
    last_time  = end_dt   - timedelta(minutes=1.5)
    total_gap  = (last_time - first_time).total_seconds()
    interval   = total_gap / (config.LECTURE_PHOTO_COUNT - 1)

    photo_times = []
    for i in range(config.LECTURE_PHOTO_COUNT):
        t = first_time + timedelta(seconds=i * interval)
        photo_times.append(t)
    return photo_times


def format_time(t):
    return datetime.combine(datetime.today(), t).strftime("%I:%M %p")


def get_full_schedule():
    now    = datetime.now().time()
    result = []
    for lecture in LECTURES:
        if now > lecture["end"]:
            status = "completed"
        elif now >= lecture["start"]:
            status = "ongoing"
        else:
            status = "upcoming"
        result.append({
            **lecture,
            "start_str": format_time(lecture["start"]),
            "end_str":   format_time(lecture["end"]),
            "status":    status
        })
    return result