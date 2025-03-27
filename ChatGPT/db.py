import json
import os
from datetime import datetime

DB_FILE = "tasks.json"

# Ensure the file exists
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump([], f)

def load_tasks():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_task(task: dict):
    tasks = load_tasks()
    task["id"] = len(tasks) + 1
    task["created_at"] = datetime.now().isoformat()
    tasks.append(task)
    with open(DB_FILE, "w") as f:
        json.dump(tasks, f, indent=4)

def get_all_tasks():
    return load_tasks()
