import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.recognize import run_recognition

if __name__ == "__main__":
    run_recognition()