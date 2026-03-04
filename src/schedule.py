from datetime import datetime, time, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── College Schedule Definition ────────────────────────────────
# Each lecture is 55 minutes
# Format: (start_hour, start_minute, subject_name)

LECTURES = [
    {"id": 1, "subject": "Lecture 1", "start": time(10, 0),  "end": time(10, 55)},
    {"id": 2, "subject": "Lecture 2", "start": time(11, 0),  "end": time(11, 55)},
    {"id": 3, "subject": "Lecture 3", "start": time(12, 0),  "end": time(12, 45)},
    # Lunch Break: 12:45 → 13:40
    {"id": 4, "subject": "Lecture 4", "start": time(13, 40), "end": time(14, 35)},
    {"id": 5, "subject": "Lecture 5", "start": time(14, 40), "end": time(15, 30)},
    # Short Break: 15:30 → 15:40
    {"id": 6, "subject": "Lecture 6", "start": time(15, 40), "end": time(16, 35)},
    {"id": 7, "subject": "Lecture 7", "start": time(16, 40), "end": time(17, 30)},
]

BREAKS = [
    {"name": "Lunch Break",  "start": time(12, 45), "end": time(13, 40)},
    {"name": "Short Break",  "start": time(15, 30), "end": time(15, 40)},
]


def get_current_lecture():
    """
    Returns the currently active lecture based on real time.
    Returns None if no lecture is active right now.
    """
    now = datetime.now().time()

    for lecture in LECTURES:
        if lecture["start"] <= now <= lecture["end"]:
            return lecture

    return None


def get_next_lecture():
    """
    Returns the next upcoming lecture based on real time.
    Returns None if no more lectures today.
    """
    now = datetime.now().time()

    for lecture in LECTURES:
        if lecture["start"] > now:
            return lecture

    return None


def get_current_break():
    """Returns the current break if one is active, else None."""
    now = datetime.now().time()

    for b in BREAKS:
        if b["start"] <= now <= b["end"]:
            return b

    return None


def get_lecture_photo_times(lecture):
    """
    Calculates the 5 photo capture times for a given lecture.
    First photo at start + 2.5 mins
    Last photo at end - 1.5 mins
    Remaining 3 evenly distributed in between.
    """
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


def get_time_until_next_lecture():
    """Returns minutes until the next lecture starts."""
    next_lec = get_next_lecture()
    if not next_lec:
        return None

    now      = datetime.now()
    today    = now.date()
    next_dt  = datetime.combine(today, next_lec["start"])
    diff     = next_dt - now

    return max(0, int(diff.total_seconds() / 60))


def get_lecture_status(lecture):
    """
    Returns how far into a lecture we are as a percentage.
    Useful for progress bar on dashboard.
    """
    now      = datetime.now()
    today    = now.date()
    start_dt = datetime.combine(today, lecture["start"])
    end_dt   = datetime.combine(today, lecture["end"])

    total    = (end_dt - start_dt).total_seconds()
    elapsed  = (now - start_dt).total_seconds()

    return min(100, max(0, round((elapsed / total) * 100)))


def format_time(t):
    """Formats a time object to 12hr format string like 10:00 AM."""
    return datetime.combine(datetime.today(), t).strftime("%I:%M %p")


def get_full_schedule():
    """Returns the full day schedule with status for each lecture."""
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
            "start_str" : format_time(lecture["start"]),
            "end_str"   : format_time(lecture["end"]),
            "status"    : status
        })

    return result