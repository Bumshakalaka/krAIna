"""Base class for skills."""
import logging
from pathlib import Path
from pprint import pprint

import yaml
from dotenv import load_dotenv, find_dotenv

from libs.utils import import_module
from skills.skill import BaseSkill

logger = logging.getLogger(__name__)


class Skills(dict):
    """Base skills."""

    def __init__(self):
        """
        Initialize skills.

        Iterate over all folders inside skills folder.
        skills/
        ├── fix
        │     ├── prompt.md - skill system prompt, required
        │     ├── config.yaml - skill LLM settings, optional
        │     ├── py_module.py - overwrite default behaviour of skill, specialisation - must be defined in model.yaml
        """
        super().__init__()
        for skill in Path(__file__).parent.glob("*"):
            if not (skill.is_dir() and (skill / "prompt.md").exists()):
                logger.debug(f"This is not skill folder:{skill}")
                continue
            skill_cls = BaseSkill
            settings = {}
            if (skill / "config.yaml").exists():
                with open(skill / "config.yaml") as fd:
                    settings = yaml.safe_load(fd.read())
                if settings.get("specialisation", None):
                    if (
                        _file := (
                            skill / settings["specialisation"].get("file", "not_exists")
                        )
                    ).exists():
                        skill_cls = getattr(
                            import_module(_file), settings["specialisation"]["class"]
                        )
                    del settings["specialisation"]
            else:
                logger.debug(
                    f"{skill.name} does not use config.yaml, default will be used."
                )
            with open(skill / "prompt.md") as fd:
                self[skill.name] = skill_cls(
                    name=skill.name, prompt=fd.read(), **settings
                )


if __name__ == "__main__":
    load_dotenv(find_dotenv())
    skills = Skills()
    pprint(skills)
    action = skills["fix"]
    print(action.run("cos ciekawego"))
