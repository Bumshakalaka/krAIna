"""Base assistant class."""
import enum
import logging
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from typing import Union, List, Dict, Optional, Callable

from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from libs.db.controller import Db, LlmMessageType
from libs.llm import chat_llm
from tools.base import get_and_init_tools

logger = logging.getLogger(__name__)

SPECIALIZED_ASSISTANT = {}

DummyBaseMessage = namedtuple("Dummy", "content response_metadata")


class AssistantType(enum.Enum):
    """Assistant type."""

    SIMPLE = "simple"
    WITH_TOOLS = "with_tools"


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
    """Max token response"""
    callbacks: Dict[str, Optional[Callable]] = field(
        default_factory=lambda: dict(action=None, observation=None, output=None), init=True
    )
    """Set of callbacks for assistant with tools"""
    type: AssistantType = AssistantType.SIMPLE  # simple, with_tools
    """Type of assistant"""
    tools: List[str] = None
    """Tools to use"""
    force_api: str = None  # azure, openai
    """Force to use azure or openai"""

    def __init_subclass__(cls, **kwargs):
        """
        Automatically add all subclasses of this class to `SPECIALIZED_ASSISTANT` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_ASSISTANT[cls.__name__] = cls

    def run(self, query: str, use_db=True, conv_id: Union[int, None] = None, **kwargs) -> AssistantResp:
        """
        Query LLM as assistant.

        Assistant uses the database to handle chat history.

        :param query: Text which is passed as Human text to LLM chat.
        :param use_db: Use long-term memory of not. Default is True.
        :param conv_id: Conversation ID. If None, new conversation is started
        :param kwargs: Additional key-value pairs to substitute in System prompt
        :return: AssistantResp dataclass
        """
        logger.info(f"{self.name}: {query=}, {kwargs=}")
        ai_db = None
        if use_db:
            ai_db = Db()
            if conv_id:
                # TODO: validate conv_id. If not exists, create new_conversation
                ai_db.conv_id = conv_id
            else:
                ai_db.new_conversation(assistant=self.name)
                conv_id = ai_db.conv_id
            hist = []
            for message in ai_db.get_conversation().messages:
                if message.type == LlmMessageType.HUMAN:
                    hist.append(HumanMessage(message.message))
                elif message.type == LlmMessageType.AI:
                    # Do not append TOOL messages
                    hist.append(AIMessage(message.message))
            ai_db.add_message(LlmMessageType.HUMAN, query)
        else:
            hist = []
            conv_id = None
        if self.type == AssistantType.SIMPLE:
            ret = self._run_simple_assistant(query, hist, ai_db, **kwargs)
        else:
            ret = self._run_assistant_with_tools(query, hist, ai_db, **kwargs)
        ai_db.add_message(LlmMessageType.AI, ret.content) if ai_db else None
        logger.info(f"{self.name}: ret={ret}")
        return AssistantResp(conv_id, ret)

    def _run_simple_assistant(self, query: str, hist: List, ai_db: Db, **kwargs) -> BaseMessage:
        """Run a simple assistant query."""
        chat = chat_llm(
            force_api_type=self.force_api,
            model=self.model,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                MessagesPlaceholder("hist") if hist else ("human", ""),
                ("human", "{text}"),
            ]
        )
        return chat.invoke(prompt.format_prompt(text=query, hist=hist, **kwargs))

    def _run_assistant_with_tools(
        self, query: str, hist: List, ai_db: Db, **kwargs
    ) -> Union[BaseMessage, DummyBaseMessage]:
        """Run an assistant with the tools query."""
        llm = chat_llm(
            force_api_type=self.force_api,
            model=self.model,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                MessagesPlaceholder("chat_history") if hist else ("human", ""),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        tools = get_and_init_tools(self.tools)
        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        chunks = []
        for chunk in agent_executor.stream(
            dict({"input": query, "chat_history": hist, "date": datetime.now().strftime("%Y-%m-%d")}, **kwargs)
        ):
            chunks.append(chunk)
            # Agent Action
            if "actions" in chunk:
                for action in chunk["actions"]:
                    msg = f"Invoking Tool: '{action.tool}' with input '{action.tool_input}'"
                    ai_db.add_message(LlmMessageType.TOOL, msg) if ai_db else None
                    self.callbacks["action"](msg) if self.callbacks["action"] else None
            # Observation
            elif "steps" in chunk:
                for step in chunk["steps"]:
                    msg = f"Tool Result: `{step.observation}`"
                    ai_db.add_message(LlmMessageType.TOOL, msg) if ai_db else None
                    self.callbacks["observation"](msg) if self.callbacks["observation"] else None
            # Final result
            elif "output" in chunk:
                self.callbacks["output"](chunk["output"]) if self.callbacks["output"] else None
            else:
                raise ValueError()
        # TODO: fix it, do not return dummy structure
        # TODO: get used tokens
        return DummyBaseMessage(chunks[-1]["messages"][0].content, dict(token_usage={}, model_name=self.model))
