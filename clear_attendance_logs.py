import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.attendance import clear_all_csv_logs

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete ALL CSV logs? (yes/no): ")
    if confirm.lower() == "yes":
        clear_all_csv_logs()
    else:
        print("[CANCELLED] No files deleted")