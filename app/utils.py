import os
import random
from werkzeug.utils import secure_filename

def allowed_file(filename: str, allowed_exts: set) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_exts

def initials_from_name(name: str) -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "NA"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

def avatar_color(seed: str) -> str:
    # deterministic-ish pastel palette
    palette = ["#5bb2f5", "#42c93a", "#f69050", "#b46cff", "#ff4d6d", "#00b8d9", "#ffb703", "#4361ee"]
    idx = sum([ord(c) for c in (seed or "x")]) % len(palette)
    return palette[idx]

def secure_save(file_storage, upload_dir: str, filename_hint: str) -> str:
    os.makedirs(upload_dir, exist_ok=True)
    safe = secure_filename(filename_hint)
    path = os.path.join(upload_dir, safe)
    # ensure uniqueness
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = f"{base}_{n}{ext}"
        n += 1
    file_storage.save(path)
    # return normalized path for DB
    return path.replace("\\", "/")
