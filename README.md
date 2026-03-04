## ⚠️ Important — Windows Setup

Do NOT use `pip install -r requirements.txt` directly on Windows.
dlib installation via pip fails on Windows without Visual Studio build tools.

Use conda instead:
    conda env create -f environment.yml
    conda activate smart_attendance

While using the photo recognition using the reconize_photo.py you need to make a file called upload_scan under the parent file and an subfile in that file called processed