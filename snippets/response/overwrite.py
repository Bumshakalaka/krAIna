"""Specialisation for response skill."""
import logging
from pathlib import Path

from snippets.snippet import BaseSnippet

logger = logging.getLogger(__name__)


class Response(BaseSnippet):
    """
    Overwritten BaseSkill class to customize run method.
    """

    def run(self, query: str, /, **kwargs) -> str:
        """
        Overwritten BaseSkill run method by adding additional context to system prompt.

        :param query:
        :param kwargs:
        :return:
        """
        about_me = ""
        if (Path(__file__).parent / "../../about_me.txt").exists():
            with open(Path(__file__).parent / "../../about_me.txt") as fd:
                about_me = fd.read()
        else:
            logger.warning("About me not found")
        return super().run(query, about_me=about_me, **kwargs)
