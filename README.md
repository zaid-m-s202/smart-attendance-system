## ⚠️ Important — Windows Setup

Do NOT use `pip install -r requirements.txt` directly on Windows.
dlib installation via pip fails on Windows without Visual Studio build tools.

Use conda instead:
    conda env create -f environment.yml
    conda activate smart_attendance