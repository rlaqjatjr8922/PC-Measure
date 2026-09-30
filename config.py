from pathlib import Path
from threading import RLock, Event
import time

HOST = "127.0.0.1"
PORT = 8010
screen = {"selected_monitor": 1}
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRIVATE = BASE_DIR / ".private"
DB = PRIVATE / "feature-state.sqlite3"
KILL_SWITCH = False
lock = RLock()
input_lock = RLock()
stop_event = Event()
held_keys = set()
held_buttons = set()
started = time.monotonic()

BYPASS_HITL = False
stats = {"requests": 0, "errors": 0, "duration_ms": 0.0}
