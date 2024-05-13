"""Base assistant class."""
import logging
from dataclasses import dataclass
from typing import List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from libs.llm import chat_llm

logger = logging.getLogger(__name__)

SPECIALIZED_ASSISTANT = {}


@dataclass(eq=False)
class BaseAssistant:
    """
    Base class for all assistants.
    """

    name: str = ""
    prompt: str = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 512

    def __init_subclass__(cls, **kwargs):
        """
        Automatically add all subclasses of this class to `SPECIALIZED_ASSISTANT` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_ASSISTANT[cls.__name__] = cls

    def run(self, query: str, hist: List = None, /, **kwargs):
        """
        Run the skill with user query.

        :param query: text which is passed as Human text to LLM chat.
        :param hist: Chat history
        :param kwargs: additional key-value pairs to substitute in System prompt
        :return:
        """
        logger.info(f"{self.name}: {query=}, {kwargs=}")
        chat = chat_llm(
            model=self.model, temperature=self.temperature, max_tokens=self.max_tokens
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                MessagesPlaceholder("hist") if hist else ("human", ""),
                ("human", "{text}"),
            ]
        )
        ret = chat.invoke(prompt.format_prompt(text=query, hist=hist, **kwargs))
        logger.info(f"{self.name}: ret={ret}")
        return ret.content
