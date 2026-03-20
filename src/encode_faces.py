def encode_known_faces():
    print("\n Starting face encoding process...")
    print(f" Looking for faces in: {config.KNOWN_FACES_DIR}")

    # ── Guard — check student_faces/ exists ────────────────────
    if not os.path.exists(config.KNOWN_FACES_DIR):
        print(f"[ERROR] student_faces/ folder not found at: {config.KNOWN_FACES_DIR}")
        print("        Create it and add one subfolder per student with their photos.")
        return

    known_encodings = []
    known_names     = []
    known_ids       = []

    # rest of the function stays exactly the same...