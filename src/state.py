import threading
import sys
import os
import json
from pathlib import Path
from typing import Optional
import datetime

# --- Global State ---
USER_LOGS = {} 
USER_PROGRESS = {}
LOCK = threading.RLock()

# --- Configuration Constants ---
TEMP_DIR = Path("/tmp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# --- Helper Functions for State ---
def get_progress(uid):
    with LOCK:
        return USER_PROGRESS.get(uid, {"percent": 0, "text": "System Idle", "status": "idle"})

def update_progress(uid, percent, text, status):
    with LOCK:
        USER_PROGRESS[uid] = {"percent": percent, "text": text, "status": status}

def get_user_temp_dir(uid) -> Path:
    """Creates and returns a specific directory for the logged-in user."""
    user_dir = TEMP_DIR / uid
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

# --- Pending File Manifest ---
MANIFEST_FILENAME = ".manifest.json"

def _manifest_path(uid) -> Path:
    return get_user_temp_dir(uid) / MANIFEST_FILENAME

def _read_manifest(uid) -> dict:
    path = _manifest_path(uid)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_manifest(uid, data: dict):
    path = _manifest_path(uid)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)  # atomic on POSIX
    except Exception as e:
        print(f"   Could not write manifest for {uid}: {e}")

def set_pending_file(uid, role: str, path: Path):
    with LOCK:
        data = _read_manifest(uid)
        old_path_str = data.get(role)
        if old_path_str and old_path_str != str(path):
            old_path = Path(old_path_str)
            if old_path.exists():
                try:
                    old_path.unlink()
                    print(f"   Removed superseded {role} file: {old_path.name}")
                except Exception as e:
                    print(f"   Could not remove superseded {role} file: {e}")
        data[role] = str(path)
        _write_manifest(uid, data)

def get_pending_files(uid) -> dict:
    with LOCK:
        data = _read_manifest(uid)
    result = {}
    for role, p in data.items():
        path = Path(p)
        if path.exists():
            result[role] = path
    return result

def clear_pending_file(uid, role: str):
    with LOCK:
        data = _read_manifest(uid)
        if role in data:
            data.pop(role, None)
            _write_manifest(uid, data)

# --- Per-user Task Lock ---
ACTIVE_TASKS = {} 

def try_start_task(uid, task_name: str) -> bool:
    with LOCK:
        if uid in ACTIVE_TASKS:
            return False
        ACTIVE_TASKS[uid] = task_name
        return True

def end_task(uid):
    with LOCK:
        ACTIVE_TASKS.pop(uid, None)

def get_active_task(uid) -> Optional[str]:
    with LOCK:
        return ACTIVE_TASKS.get(uid)

# --- Log Capture System ---
class LogCatcher:
    
    def __init__(self, original_stream):
        self.terminal = original_stream

    def write(self, msg):
        self.terminal.write(msg)
        if msg and msg.strip():
            # Identify user by thread name (set in run_background_task)
            thread_name = threading.current_thread().name
            
            # Only capture logs for worker threads named "user_..."
            if thread_name.startswith("user_"):
                uid = thread_name.replace("user_", "")
                
                with LOCK:
                    if uid not in USER_LOGS:
                        USER_LOGS[uid] = []
                    
                    USER_LOGS[uid].append(msg)
                    if len(USER_LOGS[uid]) > 500:
                        USER_LOGS[uid].pop(0)

    def flush(self):
        self.terminal.flush()

# Apply the LogCatcher immediately when this module is imported
sys.stdout = LogCatcher(sys.stdout)