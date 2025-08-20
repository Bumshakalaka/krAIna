"""Specialisation for response skill."""

import base64
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from kraina.libs.llm import chat_llm
from kraina.snippets.snippet import BaseSnippet

logger = logging.getLogger(__name__)


class Response(BaseSnippet):
    """Overwritten BaseSkill class to customize run method."""

    def run(self, query: str, /, **kwargs) -> str:
        """Overwritten BaseSkill run method by adding additional context to system prompt.

        :param query:
        :param kwargs:
        :return:
        """
        logger.info(f"{self.name}: {query=}, {kwargs=}")
        if not (Path(query).is_file() and Path(query).exists()):
            raise FileNotFoundError(query)

        with open(Path(query), "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        chat = chat_llm(model=self.model, temperature=self.temperature, max_tokens=self.max_tokens)
        content = [
            {"type": "text", "text": self.prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
            },
        ]
        ret = chat.invoke([HumanMessage(content=content)])  # type: ignore
        logger.info(f"{self.name}: ret={ret}")
        return ret.content  # type: ignore
