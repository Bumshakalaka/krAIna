import sys
from pathlib import Path

APP_DIR = Path(sys.argv[0]).parent
CONFIG_FILE = (APP_DIR / "config.yaml").resolve()
ENV_FILE = (APP_DIR / ".env").resolve()
STORE_PATH = (APP_DIR / ".store_files").resolve()
STORE_PATH_IMAGES = (STORE_PATH / "images").resolve()
STORE_PATH_IMAGES.mkdir(parents=True, exist_ok=True)

STORE_PATH.mkdir(parents=True, exist_ok=True)
