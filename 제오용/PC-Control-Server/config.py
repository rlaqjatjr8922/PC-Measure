from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"
LOG_DIR = DATA_DIR / "logs"

PLUGINS_DIR = BASE_DIR / "plugins"


server = {
    "host": "0.0.0.0",
    "port": 8002,
    "debug": True,
}


security = {
    "api_key": None,
}


paths = {
    "history": HISTORY_DIR,
    "logs": LOG_DIR,
    "plugins": PLUGINS_DIR,
}


HISTORY_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

# Discord connection settings (private).
DISCORD_BOT_TOKEN = 'MTU1NTE2MjY0MjY5MDA4NDkyNA.GELG9H.-NOUGvOz4MLISb3IRiwB77CA8aeFTMn1m2zCKE'
DISCORD_CHANNEL_ID = '1551901545967394826'
REMOTE_PC_CODE = '0001'
