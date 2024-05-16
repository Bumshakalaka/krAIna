"""Base assistant class."""
import logging
from dataclasses import dataclass
from typing import Union

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from libs.db.controller import Db
from libs.llm import chat_llm

logger = logging.getLogger(__name__)

SPECIALIZED_ASSISTANT = {}


@dataclass(eq=False)
class AssistantResp:
    """Assistant response dataclass."""

    conv_id: int
    """conversion ID"""
    data: BaseMessage
    """LLM Response in langChain BaseMessage"""


@dataclass(eq=False)
class BaseAssistant:
    """
    Base class for all assistants.
    """

    name: str = ""
    """Assistant name"""
    description: str = ""
    """Description of the assistant"""
    prompt: str = None
    """Assistant system prompt"""
    model: str = "gpt-3.5-turbo"
    """Assistant LLM model"""
    temperature: float = 0.7
    """Assistant temperature"""
    max_tokens: int = 512
    """MAx token response"""

    def __init_subclass__(cls, **kwargs):
        """
        Automatically add all subclasses of this class to `SPECIALIZED_ASSISTANT` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_ASSISTANT[cls.__name__] = cls

    def run(self, query: str, conv_id: Union[int, None] = None, /, **kwargs) -> AssistantResp:
        """
        Query LLM as assistant.

        Assistant uses the database to handle chat history.

        :param query: text which is passed as Human text to LLM chat.
        :param conv_id: Conversation ID. If None, new conversation is started
        :param kwargs: additional key-value pairs to substitute in System prompt
        :return: AssistantResp dataclass
        """
        logger.info(f"{self.name}: {query=}, {kwargs=}")
        ai_db = Db()
        chat = chat_llm(
            model=self.model,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
        )
        if conv_id:
            # TODO: validate conv_id. If not exists, create new_conversation
            ai_db.conv_id = conv_id
        else:
            ai_db.new_conversation()
        conversation = ai_db.get_conversation()
        hist = []
        for message in conversation.messages:
            hist.append(HumanMessage(message.message) if message.human else AIMessage(message.message))
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                MessagesPlaceholder("hist") if hist else ("human", ""),
                ("human", "{text}"),
            ]
        )
        ai_db.add_message(True, query)
        ret = chat.invoke(prompt.format_prompt(text=query, hist=hist, **kwargs))
        ai_db.add_message(False, ret.content)
        logger.info(f"{self.name}: ret={ret}")
        return AssistantResp(ai_db.conv_id, ret)
