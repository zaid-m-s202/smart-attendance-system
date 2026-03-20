# SmartAttend — AI & IoT Based Automated Attendance System

Facial recognition based attendance system. Students are identified from photos or a live webcam feed and marked present automatically — no roll calls, no manual registers.

---

## Stack

Python 3.9 · Flask · face_recognition (dlib ResNet-34) · OpenCV · SQLite · ESP32-CAM (in progress)

---

## Setup

> dlib won't install via pip on Windows without Visual Studio Build Tools. Use conda.
```bash
git clone https://github.com/your-username/smart_attend.git
cd smart_attend
conda env create -f environment.yml
conda activate smart_Attendance
```

### Enroll students

Add a folder per student under `student_faces/` and update `data/students.csv`:
```csv
student_id,name,folder_name,class
001,Shrinivas P,shrinivas_p,Computer Science
```

Then generate encodings:
```bash
python src/encode_faces.py
```

### Run
```bash
python app.py        # web dashboard
python main.py       # standalone webcam mode
```

---

## Configuration

Everything is in `config.py`. The ones you'll actually need to change:

| Setting | Default | Note |
|---|---|---|
| `CAMERA_INDEX` | `1` | 0 = built-in, 1 = USB webcam |
| `TOLERANCE` | `0.45` | Lower = stricter matching |
| `MODEL` | `"hog"` | hog = CPU, cnn = GPU |

---

## Modes

| Mode | How | Saves to |
|---|---|---|
| Demo | 5 photos over 20 seconds | demo.db |
| Lecture | 5 photos distributed across 55 mins | lecture.db |
| Upload | Upload up to 5 photos via dashboard | upload.db |
| Burst | CLI — 5 second countdown, one photo | CSV log |

**Threshold** — student must appear in 3 of 5 photos to be marked Present.

---

## Schedule

Edit `LECTURES` in `src/schedule.py` to match your timetable.

---

## Limitations

- Reliable at 0.5–2m range — built for door kiosk or lab bench, not wide classrooms

- `encodings.pkl` is gitignored — run `encode_faces.py` on each machine after cloning
