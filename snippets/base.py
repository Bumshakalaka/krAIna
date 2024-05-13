"""Base class for snippets."""
import logging
from pathlib import Path
from pprint import pprint

import yaml
from dotenv import load_dotenv, find_dotenv

from libs.utils import import_module
from snippets.snippet import BaseSnippet

logger = logging.getLogger(__name__)


class Snippets(dict):
    """Base snippets."""

    def __init__(self):
        """
        Initialize snippets.

        Iterate over all folders inside snippets folder.
        snippets/
        ├── fix
        │     ├── prompt.md - snippet system prompt, required
        │     ├── config.yaml - snippet LLM settings, optional
        │     ├── py_module.py - overwrite default behaviour of snippet, specialisation - must be defined in model.yaml
        """
        super().__init__()
        for snippet in Path(__file__).parent.glob("*"):
            if not (snippet.is_dir() and (snippet / "prompt.md").exists()):
                logger.debug(f"This is not snippet folder:{snippet}")
                continue
            snippet_cls = BaseSnippet
            settings = {}
            if (snippet / "config.yaml").exists():
                with open(snippet / "config.yaml") as fd:
                    settings = yaml.safe_load(fd.read())
                if settings.get("specialisation", None):
                    if (
                        _file := (
                            snippet
                            / settings["specialisation"].get("file", "not_exists")
                        )
                    ).exists():
                        snippet_cls = getattr(
                            import_module(_file), settings["specialisation"]["class"]
                        )
                    del settings["specialisation"]
            else:
                logger.debug(
                    f"{snippet.name} does not use config.yaml, default will be used."
                )
            with open(snippet / "prompt.md") as fd:
                self[snippet.name] = snippet_cls(
                    name=snippet.name, prompt=fd.read(), **settings
                )


if __name__ == "__main__":
    load_dotenv(find_dotenv())
    snippets = Snippets()
    pprint(snippets)
    action = snippets["fix"]
    print(action.run("cos ciekawego"))