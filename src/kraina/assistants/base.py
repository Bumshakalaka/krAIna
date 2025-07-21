"""Base class for assistants."""

import logging
from pathlib import Path
from typing import Dict, TypeAlias

import yaml

from kraina.assistants.assistant import AssistantType, BaseAssistant
from kraina.libs.utils import find_assets, import_module
from kraina.tools.base import get_available_tools

logger = logging.getLogger(__name__)


class Assistants(Dict[str, BaseAssistant]):
    """Base assistants."""

    def __init__(self):
        """Initialize assistants.

        Iterate over all folders inside assistants folder and also search in folders
        with file tag `.kraina-land`.

        assistants/
        ├── fix
        │     ├── prompt.md - assistant system prompt, required
        │     ├── config.yaml - assistant settings, optional
        │     ├── py_module.py - overwrite default behaviour of assistant,
        │         specialisation - must be defined in model.yaml
        """
        super().__init__()
        assistant_sets = find_assets("assistants", Path(__file__).parent)

        for assistant_set in assistant_sets:
            for assistant in sorted(assistant_set.glob("*")):
                if self.get(assistant.name) is not None:
                    logger.warning(f"'{assistant.name}` assistant already exist, override it")
                if not (assistant.is_dir() and (assistant / "prompt.md").exists()):
                    logger.debug(f"This is not assistant folder:{assistant}")
                    continue
                prompt = (assistant / "prompt.md").read_text()
                assistant_cls = BaseAssistant
                settings = {}
                if (assistant / "config.yaml").exists():
                    with open(assistant / "config.yaml") as fd:
                        settings = yaml.safe_load(fd.read())
                    settings["type"] = AssistantType.SIMPLE
                    if settings.get("tools", None):
                        settings["tools"] = [x.lower() for x in settings["tools"]]
                        if not set(settings["tools"]).issubset(get_available_tools()):
                            raise KeyError(
                                f"[{assistant.name}] One of the tools={settings['tools']} is "
                                f"unsupported. Supported tools: {get_available_tools()}"
                            )
                        settings["type"] = AssistantType.WITH_TOOLS
                    contexts = []
                    if settings.get("contexts", None):
                        for name, context in settings["contexts"].items():
                            context = [context] if isinstance(context, str) else context
                            name = name.lower()
                            if "string" in name:
                                contexts.extend(
                                    context
                                    if "_template" in name
                                    else [x.replace("{", "{{").replace("}", "}}") for x in context]
                                )
                            if "file" in name:
                                for context_ in context:
                                    fd = ((assistant / "config.yaml").parent / context_).resolve()
                                    if not fd.exists():
                                        logger.warning(f"[{assistant.name}] context.file={fd} does not exist")
                                    else:
                                        if "_template" in name:
                                            contexts.append(fd.read_text().replace("{", "{{").replace("}", "}}"))
                                        else:
                                            contexts.append(fd.read_text())
                    contexts.append("Current date: {date}")
                    settings["contexts"] = contexts

                    prompt += "\nTake into consideration the context below while generating answers.\n# Context:"
                    for idx, context in enumerate(contexts):
                        prompt += f"\n## {idx}"
                        prompt += "\n" + context

                    if settings.get("model", None):
                        settings["_model"] = settings.pop("model")

                    if settings.get("specialisation", None):
                        if (_file := (assistant / settings["specialisation"].get("file", "not_exists"))).exists():
                            assistant_cls = getattr(import_module(_file), settings["specialisation"]["class"])
                        del settings["specialisation"]
                else:
                    logger.debug(f"{assistant.name} does not use config.yaml, default will be used.")
                self[assistant.name] = assistant_cls(name=assistant.name, path=assistant, prompt=prompt, **settings)


A: TypeAlias = BaseAssistant
