import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.recognize import run_recognition
from src.attendance import start_cleanup_scheduler

if __name__ == "__main__":
    # Start background cleanup — deletes CSV logs older than 12 hours
    start_cleanup_scheduler()

    # Start recognition system
    run_recognition()
