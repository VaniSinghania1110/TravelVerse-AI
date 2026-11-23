import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

candidates = [
    os.path.join(parent_dir, "backend"),
    os.path.join(parent_dir, "tvagent-main", "backend"),
    os.path.join(current_dir, "..", "backend"),
    os.path.join(current_dir, "backend")
]

for b_dir in candidates:
    if os.path.exists(b_dir) and b_dir not in sys.path:
        sys.path.insert(0, b_dir)
        break

from main import app

handler = app
