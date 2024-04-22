import logging
from dataclasses import dataclass

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

SPECIALIZED_SKILLS = {}


@dataclass(eq=False)
class BaseSkill:
    """
    Base class for all skills.
    """

    prompt: str = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.5
    max_tokens: int = 512

    def __init_subclass__(cls, **kwargs):
        """
        Automatically add all subclasses of this class to `SPECIALIZED_SKILLS` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_SKILLS[cls.__name__] = cls

    def run(self, query: str, /, **kwargs) -> str:
        """
        Run the skill with user query.

        :param query: text which is passed as Human text to LLM chat.
        :param kwargs: additional key-value pairs to substitute in System prompt
        :return:
        """
        chat = ChatOpenAI(
            model=self.model, temperature=self.temperature, max_tokens=self.max_tokens
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                ("human", "{text}"),
            ]
        )
        ret = chat.invoke(prompt.format_prompt(text=query, **kwargs))
        logger.debug(ret)
        return ret.content
