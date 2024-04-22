"""Specialisation for response skill."""
import logging
from pathlib import Path

from skills.skill import BaseSkill

logger = logging.getLogger(__name__)


class Response(BaseSkill):
    """
    Overwritten BaseSkill class to customize run method.
    """

    def run(self, text: str, /, **kwargs) -> str:
        """
        Overwritten BaseSkill run method by adding additional context to system prompt.

        :param text:
        :param kwargs:
        :return:
        """
        about_me = ""
        if (Path(__file__).parent / "../../about_me.txt").exists():
            with open(Path(__file__).parent / "../../about_me.txt") as fd:
                about_me = fd.read()
        else:
            logger.warning("About me not found")
        return super().run(text, about_me=about_me, **kwargs)
