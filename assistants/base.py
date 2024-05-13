"""Base class for assistants."""
import logging
import sys
from pathlib import Path
from pprint import pprint

import yaml
from dotenv import load_dotenv, find_dotenv

from libs.utils import import_module
from assistants.assistant import BaseAssistant

logger = logging.getLogger(__name__)


class Assistants(dict):
    """Base assistants."""

    def __init__(self):
        """
        Initialize assistants.

        Iterate over all folders inside assistants folder.
        assistants/
        ├── fix
        │     ├── prompt.md - assistant system prompt, required
        │     ├── config.yaml - assistant LLM settings, optional
        │     ├── py_module.py - overwrite default behaviour of assistant, specialisation - must be defined in model.yaml
        """
        super().__init__()
        for assistant in Path(__file__).parent.glob("*"):
            if not (assistant.is_dir() and (assistant / "prompt.md").exists()):
                logger.debug(f"This is not assistant folder:{assistant}")
                continue
            assistant_cls = BaseAssistant
            settings = {}
            if (assistant / "config.yaml").exists():
                with open(assistant / "config.yaml") as fd:
                    settings = yaml.safe_load(fd.read())
                if settings.get("specialisation", None):
                    if (
                        _file := (
                            assistant
                            / settings["specialisation"].get("file", "not_exists")
                        )
                    ).exists():
                        assistant_cls = getattr(
                            import_module(_file), settings["specialisation"]["class"]
                        )
                    del settings["specialisation"]
            else:
                logger.debug(
                    f"{assistant.name} does not use config.yaml, default will be used."
                )
            with open(assistant / "prompt.md") as fd:
                self[assistant.name] = assistant_cls(
                    name=assistant.name, prompt=fd.read(), **settings
                )


if __name__ == "__main__":
    load_dotenv(find_dotenv())
    assistants = Assistants()
    pprint(assistants)
    action = assistants["echo"]
    print(action.run("Napisz coś ciekawego"))
