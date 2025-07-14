"""Base assistant class."""

import enum
import json
import logging
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type, Union

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel
from tiktoken import Encoding, encoding_for_model, get_encoding

from kraina.libs.db.controller import Db, LlmMessageType
from kraina.libs.langfuse import langfuse_handler
from kraina.libs.llm import chat_llm, map_model
from kraina.libs.utils import IMAGE_DATA_URL_MARKDOWN_RE
from kraina.tools.base import get_and_init_tools

logger = logging.getLogger(__name__)

SPECIALIZED_ASSISTANT = {}
ADDITIONAL_TOKENS_PER_MSG = 3

DummyBaseMessage = namedtuple("Dummy", "content response_metadata")


class AssistantType(enum.Enum):
    """Assistant type."""

    SIMPLE = "simple"
    WITH_TOOLS = "with_tools"


@dataclass(eq=False)
class AssistantResp:
    """Assistant response dataclass."""

    conv_id: Union[int, None]
    """conversion ID"""
    content: Union[str, Type[BaseModel]]
    """LLM Response"""
    tokens: Dict[str, int]
    """LLM token usage in Dict"""
    error: Union[str, None] = None
    """LLM error string"""


@dataclass(eq=False)
class BaseAssistant:
    """Base class for all assistants."""

    name: str = ""
    """Assistant name"""
    description: str = ""
    """Description of the assistant"""
    prompt: str = ""
    """Assistant system prompt"""
    _model: str = "B"
    """Assistant LLM model"""
    temperature: float = 0.7
    """Assistant temperature"""
    max_tokens: int = 512
    """Max token response"""
    callbacks: Dict[str, Optional[Callable]] = field(
        default_factory=lambda: dict(action=None, observation=None, ai_observation=None, output=None), init=True
    )
    """Set of callbacks for assistant with tools"""
    type: AssistantType = AssistantType.SIMPLE  # simple, with_tools
    """Type of assistant"""
    tools: List[str] = None
    """Tools to use"""
    force_api: str = None  # azure, openai, anthropic
    """Force to use azure or openai or anthropic"""
    contexts: List[str] = None
    """List of additional contexts to be added to system prompt"""
    path: Path = None
    """Path to the assistant folder."""
    json_mode: bool = False
    """Force LLM to output in json_object format"""
    pydantic_output: Type[BaseModel] = None
    """Serialize JSON output into Pydantic model. The best is to use with json_mode"""

    def __init_subclass__(cls, **kwargs):
        """Automatically add all subclasses of this class to `SPECIALIZED_ASSISTANT` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_ASSISTANT[cls.__name__] = cls

    @property
    def encoding(self) -> Encoding:
        try:
            return encoding_for_model(self.model)
        except KeyError:
            return get_encoding("cl100k_base")

    @property
    def model(self) -> str:
        return map_model(self._model, self.force_api)

    @model.setter
    def model(self, value: str):
        self._model = value

    @lru_cache(maxsize=256)
    def _calc_tokens(self, text) -> int:
        """Calculate number of tokens from text.

        :param text:
        :return:
        """
        return len(self.encoding.encode(text))

    def tokens_used(
        self, conv_id: Union[int, None] = None, hist: Union[List[BaseMessage], None] = None
    ) -> Dict[str, int]:
        """:param conv_id: Conversation Id. If None, only number of tokens per prompts are returned
        :param hist: Use provided conversation history or get from db is None
        :return: Dict
        """
        ret = {
            "api": {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temp": self.temperature,
            },
            "prompt": 0,
            "history": 0,
        }
        msgs = []
        for msg in self._get_history(conv_id=conv_id) if not hist else hist:
            if isinstance(msg.content, str):
                msgs.append(msg.content)
            else:
                # list of dicts
                for el in msg.content:
                    if el["type"] == "text":
                        msgs.append(el["text"])
        ret["prompt"] += self._calc_tokens(self.prompt) + ADDITIONAL_TOKENS_PER_MSG
        if self.tools:
            for tool in get_and_init_tools(self.tools, self):
                ret["prompt"] += self._calc_tokens(json.dumps(convert_to_openai_tool(tool)))
        ret["history"] += sum([self._calc_tokens(msg) for msg in msgs]) + len(msgs) * ADDITIONAL_TOKENS_PER_MSG
        return ret

    def _get_history(self, conv_id: Union[int, None] = None) -> List[BaseMessage]:
        ai_db = Db()
        if conv_id is None:
            return []
        if not ai_db.is_conversation_id_valid(conv_id):
            return []
        hist = []
        for message in ai_db.get_conversation(conv_id).messages:
            if message.type == LlmMessageType.HUMAN:
                hist.append(HumanMessage(content=self._format_message(message.message)))
            elif message.type == LlmMessageType.AI:
                # Do not append TOOL messages
                hist.append(AIMessage(content=self._format_message(message.message, image_data=False)))
        return hist

    @staticmethod
    def _format_message(msg: str, image_data=True) -> List[Dict]:
        """Format a message containing text and image markdown into a list of dictionaries.

        This function scans the input message for image markdown patterns and splits the
        message into text and image segments. Each segment is stored in a dictionary with
        keys indicating the type of content.

        :param msg: The input message string containing text and image markdown.
        :return: A list of dictionaries representing formatted message segments.
        """
        # Handle empty messages
        if not msg:
            return [{"type": "text", "text": "."}]
        content = []
        start_idx = 0
        for m in IMAGE_DATA_URL_MARKDOWN_RE.finditer(msg):
            img_start = m.start(0)
            if img_start > 0:
                content.append(dict(type="text", text=msg[start_idx:img_start]))
            start_idx = m.end(0)
            if image_data:
                content.append(dict(type="image_url", image_url=dict(url=m.group("img_data"))))
            else:
                content.append(dict(type="text", text="generated image cannot be put here because of size"))
        if msg[start_idx:]:
            content.append(dict(type="text", text=msg[start_idx:]))
        return content

    def run(self, query: str, use_db=True, conv_id: Union[int, None] = None, **kwargs) -> AssistantResp:
        """Query LLM as assistant.

        Assistant uses the database to handle chat history.

        :param query: Text which is passed as Human text to LLM chat.
        :param use_db: Use long-term memory of not. Default is True.
        :param conv_id: Conversation ID. If None, new conversation is started
        :param kwargs: Additional key-value pairs to substitute in System prompt
        :return: AssistantResp dataclass
        """
        logger.info(f"{self.name}: query={query[0:80]}..., {kwargs=}")
        ai_db = None
        if use_db:
            ai_db = Db()
            if conv_id:
                ai_db.conv_id = conv_id
            else:
                ai_db.new_conversation(assistant=self.name)
                conv_id = ai_db.conv_id
            hist = self._get_history(conv_id)
            ai_db.add_message(LlmMessageType.HUMAN, query)
        else:
            hist = []
            conv_id = None

        used_tokens = self.tokens_used(conv_id, hist)
        used_tokens["input"] = len(self.encoding.encode(query)) + ADDITIONAL_TOKENS_PER_MSG
        used_tokens["total_input"] = used_tokens["prompt"] + used_tokens["history"] + used_tokens["input"]
        used_tokens["output"] = 0
        if self.type == AssistantType.SIMPLE:
            ret = self._run_simple_assistant(query, hist, ai_db, used_tokens, **kwargs)
        else:
            ret = self._run_assistant_with_tools(query, hist, ai_db, used_tokens, **kwargs)
        if isinstance(ret, list):
            # anthropic returns here list of dict(text, index, type)
            ret = ret[0]["text"]
        used_tokens["output"] += len(self.encoding.encode(ret)) + ADDITIONAL_TOKENS_PER_MSG
        used_tokens["total"] = sum([v for k, v in used_tokens.items() if k != "api"])

        ai_db.add_message(LlmMessageType.AI, ret) if ai_db else None
        logger.info(f"{self.name}: ret={str(AssistantResp(conv_id, ret, used_tokens))[0:80]}...")
        return AssistantResp(
            conv_id, self.pydantic_output.model_validate_json(ret) if self.pydantic_output else ret, used_tokens
        )

    def _run_simple_assistant(self, query: str, hist: List, ai_db: Db, tokens, **kwargs) -> str:
        """Run a simple assistant query."""
        chat = chat_llm(
            force_api_type=self.force_api,
            model=self.model,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
            json_mode=self.json_mode,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                MessagesPlaceholder("hist", optional=True),
                HumanMessage(content=self._format_message(query)),
            ]
        )
        kwargs["date"] = datetime.now().strftime("%Y-%m-%d")
        if hist:
            kwargs["hist"] = hist
        return chat.invoke(
            prompt.format_prompt(**kwargs),
            config={
                "callbacks": [langfuse_handler],
            },
        ).content

    def _run_assistant_with_tools(self, query: str, hist: List, ai_db: Db, tokens, **kwargs) -> str:
        """Run an assistant with the tools query."""
        llm = chat_llm(
            force_api_type=self.force_api,
            model=self.model,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
            json_mode=self.json_mode,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                MessagesPlaceholder("chat_history", optional=True),
                HumanMessage(content=self._format_message(query)),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        kwargs["date"] = datetime.now().strftime("%Y-%m-%d")
        if hist:
            kwargs["chat_history"] = hist
        tokens["tools"] = 0
        tools = get_and_init_tools(self.tools, self)
        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)
        chunks = []
        action_msg_id = ""
        for chunk in agent_executor.stream(kwargs, config={"callbacks": [langfuse_handler]}):
            chunks.append(chunk)
            # Agent Action
            if "actions" in chunk:
                for message in chunk["messages"]:
                    if action_msg_id != message.id:
                        action_msg_id = message.id
                        tokens["output"] += len(self.encoding.encode(message.content)) + ADDITIONAL_TOKENS_PER_MSG
                        ai_db.add_message(LlmMessageType.AI, message.content) if ai_db else None
                        self.callbacks["ai_observation"](message.content) if self.callbacks["ai_observation"] else None
                for action in chunk["actions"]:
                    tokens["tools"] += (
                        len(
                            self.encoding.encode(
                                str(
                                    dict(
                                        function=dict(
                                            arguments=action.tool_input,
                                            name=action.tool,
                                            id=action.tool_call_id,
                                            index=0,
                                            type="function",
                                        )
                                    )
                                )
                            )
                        )
                        + ADDITIONAL_TOKENS_PER_MSG
                    )
                    msg = f"Invoking Tool: '{action.tool}' with input '{action.tool_input}'"
                    ai_db.add_message(LlmMessageType.TOOL, msg) if ai_db else None
                    self.callbacks["action"](msg) if self.callbacks["action"] else None
            # Observation
            elif "steps" in chunk:
                for step in chunk["steps"]:
                    tokens["tools"] += len(self.encoding.encode(step.observation)) + ADDITIONAL_TOKENS_PER_MSG
                    msg = f"Tool Result: `{step.observation}`"
                    ai_db.add_message(LlmMessageType.TOOL, msg) if ai_db else None
                    self.callbacks["observation"](msg) if self.callbacks["observation"] else None
            # Final result
            elif "output" in chunk:
                self.callbacks["output"](chunk["output"]) if self.callbacks["output"] else None
            else:
                raise ValueError
        return chunks[-1]["output"]
