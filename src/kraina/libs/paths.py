"""Path management and configuration utilities for the Kraina application.

This module handles:
- Application directory and file path definitions
- Configuration file initialization and validation
- Environment file setup
- Store directory creation and management
"""

import json
import logging
import sys
from pathlib import Path

import yaml
from jsonschema import validate

logger = logging.getLogger(__name__)

APP_DIR = Path(sys.argv[0]).parent
CONFIG_FILE = (APP_DIR / "config.yaml").resolve()
ENV_FILE = (APP_DIR / ".env").resolve()
STORE_PATH = (APP_DIR / ".store_files").resolve()
STORE_PATH_IMAGES = (STORE_PATH / "images").resolve()
STORE_PATH_IMAGES.mkdir(parents=True, exist_ok=True)

STORE_PATH.mkdir(parents=True, exist_ok=True)


def init_config_file():
    """Initialize the config file.

    If the config file does not exist, create it from the template.
    """
    # TODO: place where we can do migration of config.yaml
    # TODO: validation of config.yaml
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text((Path(__file__).parent.parent / "templates" / "config.yaml.template").read_text())


def init_env_file():
    """Initialize the env file.

    If the env file does not exist, create it from the template.
    """
    if not ENV_FILE.exists():
        ENV_FILE.write_text((Path(__file__).parent.parent / "templates" / ".env.template").read_text())


def config_file_validation():
    """Validate config.yaml against the template recursively."""
    config_schema = Path(__file__).parent.parent / "templates" / "config-schema.json"
    with open(config_schema, "r") as f:
        schema = json.load(f)
    with open(CONFIG_FILE, "r") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    validate(config, schema)


init_config_file()
config_file_validation()
init_env_file()
