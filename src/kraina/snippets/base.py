"""Base class for snippets."""

import logging
from pathlib import Path
from typing import Dict

import yaml

from kraina.libs.utils import find_assets, get_os_info, import_module
from kraina.snippets.snippet import BaseSnippet
from kraina.tools.base import get_available_tools

logger = logging.getLogger(__name__)


class Snippets(Dict[str, BaseSnippet]):
    """Base snippets."""

    def __init__(self):
        """Initialize snippets.

        Iterate over all folders inside snippets folder and also search in folders with file tag `.kraina-land`.
        snippets/
        ├── fix
        │     ├── prompt.md - snippet system prompt, required
        │     ├── config.yaml - snippet LLM settings, optional
        │     ├── py_module.py - overwrite default behaviour of snippet, specialisation - must be defined in model.yaml
        """
        super().__init__()
        snippet_sets = find_assets("snippets", Path(__file__).parent)

        for snippet_set in snippet_sets:
            for snippet in snippet_set.glob("*"):
                if self.get(snippet.name) is not None:
                    logger.warning(f"'{snippet.name}` snippet already exist, override it")
                if not (snippet.is_dir() and (snippet / "prompt.md").exists()):
                    logger.debug(f"This is not snippet folder:{snippet}")
                    continue
                prompt = (snippet / "prompt.md").read_text()
                snippet_cls = BaseSnippet
                settings = {}
                if (snippet / "config.yaml").exists():
                    with open(snippet / "config.yaml") as fd:
                        settings = yaml.safe_load(fd.read())
                    if settings.get("tools"):
                        tools = settings["tools"]
                        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
                            raise TypeError(f"[{snippet.name}] tools must be a list of strings")
                        normalized_tools = [tool.lower() for tool in tools]
                        unsupported = sorted(set(normalized_tools) - set(get_available_tools()))
                        if unsupported:
                            raise KeyError(
                                f"[{snippet.name}] Unsupported tools: {unsupported}. "
                                f"Supported tools: {get_available_tools()}"
                            )
                        settings["tools"] = normalized_tools
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
                                    fd = ((snippet / "config.yaml").parent / context_).resolve()
                                    if not fd.exists():
                                        logger.error(f"[{snippet.name}] context.file={fd} does not exist")
                                    else:
                                        if "_template" in name:
                                            contexts.append(fd.read_text().replace("{", "{{").replace("}", "}}"))
                                        else:
                                            contexts.append(fd.read_text())
                    contexts.append("Current date: {date}")
                    contexts.append("Current OS info: {" + get_os_info() + "}")
                    settings["contexts"] = contexts
                    prompt += "\nTake into consideration the context below while generating answers.\n# Context:"
                    for idx, context in enumerate(contexts):
                        prompt += f"\n## {idx}"
                        prompt += "\n" + context

                    if settings.get("model", None):
                        settings["_model"] = settings.pop("model")

                    if settings.get("specialisation", None):
                        if (_file := (snippet / settings["specialisation"].get("file", "not_exists"))).exists():
                            snippet_cls = getattr(import_module(_file), settings["specialisation"]["class"])
                        del settings["specialisation"]
                else:
                    logger.debug(f"{snippet.name} does not use config.yaml, default will be used.")
                self[snippet.name] = snippet_cls(name=snippet.name, prompt=prompt, path=snippet, **settings)
