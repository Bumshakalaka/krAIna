"""Base class for assistants."""
import logging
from pathlib import Path
from pprint import pprint

import yaml
from dotenv import load_dotenv, find_dotenv

from libs.utils import import_module, find_lands
from assistants.assistant import BaseAssistant, AssistantType
from tools.base import get_available_tools

logger = logging.getLogger(__name__)


class Assistants(dict):
    """Base assistants."""

    def __init__(self):
        """
        Initialize assistants.

        Iterate over all folders inside assistants folder and also search in folders with file tag `.kraina-land`.
        assistants/
        ├── fix
        │     ├── prompt.md - assistant system prompt, required
        │     ├── config.yaml - assistant settings, optional
        │     ├── py_module.py - overwrite default behaviour of assistant, specialisation - must be defined in model.yaml
        """
        super().__init__()
        assistant_sets = find_lands("assistants", Path(__file__).parent)

        for assistant_set in assistant_sets:
            for assistant in assistant_set.glob("*"):
                if self.get(assistant.name) is not None:
                    logger.error(f"'{assistant.name}` assistant already exist")
                    continue
                if not (assistant.is_dir() and (assistant / "prompt.md").exists()):
                    logger.debug(f"This is not assistant folder:{assistant}")
                    continue
                assistant_cls = BaseAssistant
                settings = {}
                if (assistant / "config.yaml").exists():
                    with open(assistant / "config.yaml") as fd:
                        settings = yaml.safe_load(fd.read())
                    if settings.get("type", None):
                        try:
                            settings["type"] = AssistantType[settings["type"].upper()]
                        except KeyError:
                            raise KeyError(
                                f"type={settings['type']} is invalid. Supported type: {[e.name.lower() for e in AssistantType]}"
                            )
                    if (
                        settings.get("type", None)
                        and settings["type"] == AssistantType.WITH_TOOLS
                        and settings.get("tools", None)
                    ):
                        settings["tools"] = [x.lower() for x in settings["tools"]]
                        if not set(settings["tools"]).issubset(get_available_tools()):
                            raise KeyError(
                                f"One of the tools={settings['tools']} is unsupported. Supported tools: {get_available_tools()}"
                            )
                    if settings.get("specialisation", None):
                        if (_file := (assistant / settings["specialisation"].get("file", "not_exists"))).exists():
                            assistant_cls = getattr(import_module(_file), settings["specialisation"]["class"])
                        del settings["specialisation"]
                else:
                    logger.debug(f"{assistant.name} does not use config.yaml, default will be used.")
                with open(assistant / "prompt.md") as fd:
                    self[assistant.name] = assistant_cls(name=assistant.name, prompt=fd.read(), **settings)


if __name__ == "__main__":
    load_dotenv(find_dotenv())
    assistants = Assistants()
    pprint(assistants)
    action = assistants["echo"]
    print(action.run("Napisz coś ciekawego"))
