"""Base assistant class."""

import asyncio
import enum
import json
import logging
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from tiktoken import Encoding, encoding_for_model, get_encoding

from kraina.libs.db.controller import Db, LlmMessageType
from kraina.libs.langfuse import langfuse_handler
from kraina.libs.llm import chat_llm, map_model
from kraina.libs.utils import IMAGE_DATA_URL_MARKDOWN_RE
from kraina.tools.base import get_and_init_langchain_tools, get_and_init_mcp_tools

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

    conv_id: Optional[int]
    """conversion ID"""
    content: Union[str, Type[BaseModel]]
    """LLM Response"""
    tokens: Dict[str, int]
    """LLM token usage in Dict"""
    error: Optional[str] = None
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
    tools: Optional[List[str]] = None
    """Tools to use"""
    force_api: Optional[str] = None  # azure, openai, anthropic
    """Force to use azure or openai or anthropic"""
    contexts: Optional[List[str]] = None
    """List of additional contexts to be added to system prompt"""
    path: Optional[Path] = None
    """Path to the assistant folder."""
    json_mode: bool = False
    """Force LLM to output in json_object format"""
    pydantic_output: Optional[Type[BaseModel]] = None
    """Serialize JSON output into Pydantic model. The best is to use with json_mode"""
    __buildin__: bool = False
    """If True, assistant is built-in and cannot be removed"""
    _tools_tokens: int = -1
    """Number of tokens used by tools. Updated on LLM call."""
    _initialized_tools: List[BaseTool] = field(default_factory=list)
    """Internal list of initialized MCP and langchain tools."""
    _tools_number: int = -1
    """Number of tools used by assistant."""

    def __init_subclass__(cls, **kwargs):
        """Automatically add all subclasses of this class to `SPECIALIZED_ASSISTANT` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_ASSISTANT[cls.__name__] = cls

    @property
    def used_tools(self) -> str:
        """Get the number of tools ad token usage by assistant."""
        return f"{self._tools_tokens} ({self._tools_number})"

    @property
    def encoding(self) -> Encoding:
        """Get the encoding for the model."""
        try:
            return encoding_for_model(self.model)
        except KeyError:
            return get_encoding("cl100k_base")

    @property
    def model(self) -> str:
        """Get the mapped model name."""
        return map_model(self._model, self.force_api)

    @model.setter
    def model(self, value: str):
        """Set the model name."""
        self._model = value

    @lru_cache(maxsize=256)
    def _calc_tokens(self, text) -> int:
        """Calculate number of tokens from text.

        :param text: Input text to calculate tokens for
        :return: Number of tokens
        """
        return len(self.encoding.encode(text))

    def tokens_used(self, conv_id: Optional[int] = None, hist: Optional[List[BaseMessage]] = None) -> Dict[str, int]:
        """Calculate tokens used for conversation.

        :param conv_id: Conversation Id. If None, only number of tokens per prompts are returned
        :param hist: Use provided conversation history or get from db is None
        :return: Dict with token usage information
        """
        ret = {
            "api": {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temp": self.temperature,
            },
            "prompt": 0,
            "tools_input": self.used_tools,
            "history": 0,
        }
        msgs = []
        for msg in self._get_history(conv_id=conv_id) if not hist else hist:
            if isinstance(msg.content, str):
                msgs.append(msg.content)
            else:
                # list of dicts
                for el in msg.content:
                    if isinstance(el, dict) and el.get("type") == "text":
                        msgs.append(el.get("text", ""))
        ret["prompt"] += self._calc_tokens(self.prompt) + ADDITIONAL_TOKENS_PER_MSG
        ret["history"] += sum([self._calc_tokens(msg) for msg in msgs]) + len(msgs) * ADDITIONAL_TOKENS_PER_MSG
        return ret

    def _get_history(self, conv_id: Optional[int] = None) -> List[BaseMessage]:
        """Get conversation history from database.

        :param conv_id: Conversation ID to retrieve history for
        :return: List of base messages from conversation history
        """
        ai_db = Db()
        if conv_id is None:
            return []
        if not ai_db.is_conversation_id_valid(conv_id):
            return []
        hist = []
        for message in ai_db.get_conversation(conv_id).messages:
            if message.type == LlmMessageType.HUMAN:
                hist.append(HumanMessage(content=self._format_message(message.message)))  # type: ignore
            elif message.type == LlmMessageType.AI:
                # Do not append TOOL messages
                hist.append(AIMessage(content=self._format_message(message.message, image_data=False)))  # type: ignore
        return hist

    @staticmethod
    def _format_message(msg: str, image_data=True) -> List[Dict]:
        """Format a message containing text and image markdown into a list of dictionaries.

        This function scans the input message for image markdown patterns and splits the
        message into text and image segments. Each segment is stored in a dictionary with
        keys indicating the type of content.

        :param msg: The input message string containing text and image markdown
        :param image_data: Whether to include image data in the formatted output
        :return: A list of dictionaries representing formatted message segments
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

    @staticmethod
    def _last_agent_step(response_metadata: Dict) -> bool:
        """Determine if the agent's response indicates the last step in a sequence.

        This method checks the response metadata for specific keys that indicate
        a finishing reason and returns True if the reason matches predefined stop signals.

        :param response_metadata: A dictionary containing metadata about the agent's response.
        :return: True if the response indicates the last step, False otherwise.
        """
        for reason in ["finish_reason", "stop_reason", "done_reason"]:
            if reason in response_metadata:
                finish_reason: str = response_metadata[reason]
                break
        else:
            finish_reason = "unknown"
        stop_str = ["stop", "end_turn", "stop_sequence", "done"]
        # TODO: check other LLM providers
        logger.info(response_metadata)
        return finish_reason in stop_str

    @staticmethod
    def _tool_usage_agent_step(response_metadata: Dict) -> bool:
        """Determine if the agent's response indicates the tool usage.

        This method checks the response metadata for specific keys that indicate
        a finishing reason and returns True if the reason matches predefined stop signals.

        :param response_metadata: A dictionary containing metadata about the agent's response.
        :return: True if the response indicates the tool usage, False otherwise.
        """
        for reason in ["finish_reason", "stop_reason", "done_reason"]:
            if reason in response_metadata:
                finish_reason: str = response_metadata[reason]
                break
        else:
            finish_reason = "unknown"
        stop_str = ["tool_calls", "tool_use"]
        # TODO: check other LLM providers
        logger.info(response_metadata)
        return finish_reason in stop_str

    def run(self, query: str, use_db=True, conv_id: Optional[int] = None, **kwargs) -> AssistantResp:
        """Query LLM as assistant (sync).

        This is a synchronous wrapper around the async `arun` method.
        Assistant uses the database to handle chat history.

        :param query: Text which is passed as Human text to LLM chat
        :param use_db: Use long-term memory of not. Default is True
        :param conv_id: Conversation ID. If None, new conversation is started
        :param kwargs: Additional key-value pairs to substitute in System prompt
        :return: AssistantResp dataclass
        """
        return asyncio.run(self.arun(query, use_db, conv_id, **kwargs))

    async def arun(self, query: str, use_db=True, conv_id: Optional[int] = None, **kwargs) -> AssistantResp:
        """Query LLM as assistant (async).

        Assistant uses the database to handle chat history.

        :param query: Text which is passed as Human text to LLM chat
        :param use_db: Use long-term memory of not. Default is True
        :param conv_id: Conversation ID. If None, new conversation is started
        :param kwargs: Additional key-value pairs to substitute in System prompt
        :return: AssistantResp dataclass
            The asyncio.CancelledError and asyncio.TimeoutError will return the AssistantResp with cancellation message
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
        try:
            if self.type == AssistantType.SIMPLE:
                ret = await self._run_simple_assistant(query, hist, ai_db, used_tokens, **kwargs)
            else:
                ret = await self._run_assistant_with_tools(query, hist, ai_db, used_tokens, **kwargs)

            if isinstance(ret, list):
                # anthropic returns here list of dict(text, index, type)
                if ret and isinstance(ret[0], dict) and "text" in ret[0]:
                    ret = ret[0]["text"]  # type: ignore
                else:
                    ret = str(ret)
            used_tokens["output"] += len(self.encoding.encode(ret)) + ADDITIONAL_TOKENS_PER_MSG
            used_tokens["tools_input"] = self.used_tools  # type: ignore
            used_tokens["total"] = sum([v for k, v in used_tokens.items() if k not in ["api", "tools_input"]])

            if ai_db:
                ai_db.add_message(LlmMessageType.AI, ret)
            logger.info(f"{self.name}: ret={str(AssistantResp(conv_id, ret, used_tokens))[0:80]}...")
            content = self.pydantic_output.model_validate_json(ret) if self.pydantic_output else ret
            return AssistantResp(conv_id, content, used_tokens)  # type: ignore

        except asyncio.CancelledError:
            ret = AssistantResp(conv_id, "[Execution cancelled by user]", used_tokens)
            if ai_db:
                ai_db.add_message(LlmMessageType.AI, str(ret.content))
            logger.info(f"{self.name}: {ret.content}")
            return ret
        except asyncio.TimeoutError:
            ret = AssistantResp(conv_id, "[Execution timed out]", used_tokens)
            if ai_db:
                ai_db.add_message(LlmMessageType.AI, str(ret.content))
            logger.info(f"{self.name}: {ret.content}")
            return ret

    async def _run_simple_assistant(
        self, query: str, hist: List, _ai_db: Optional[Db], _tokens: Dict[str, int], **kwargs
    ) -> str:
        """Run a simple assistant query (async).

        :param query: User query string
        :param hist: Conversation history
        :param ai_db: Database instance for conversation storage
        :param tokens: Token usage tracking
        :param kwargs: Additional keyword arguments for prompt formatting
        :return: Assistant response string
        """
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
                HumanMessage(content=self._format_message(query)),  # type: ignore
            ]
        )
        kwargs["date"] = datetime.now().strftime("%Y-%m-%d")
        if hist:
            kwargs["hist"] = hist

        response = await chat.ainvoke(
            prompt.format_prompt(**kwargs),
            config={
                "callbacks": [langfuse_handler],
            },
        )
        return response.content  # type: ignore

    async def _run_assistant_with_tools(
        self, query: str, hist: List, ai_db: Optional[Db], tokens: Dict[str, int], **kwargs
    ) -> str:
        """Run an assistant with the tools query in async.

        Async is required to have working MCP tools.

        :param query: User query string
        :param hist: Conversation history
        :param ai_db: Database instance for conversation storage
        :param tokens: Token usage tracking
        :param kwargs: Additional keyword arguments for prompt formatting
        :return: Assistant response string
        :raises: asyncio.CancelledError or asyncio.TimeoutError when execution is interrupted
        """
        llm = chat_llm(
            force_api_type=self.force_api,
            model=self.model,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
            json_mode=self.json_mode,
        )

        # Prepare prompt string with date substitution for LangGraph
        kwargs["date"] = datetime.now().strftime("%Y-%m-%d")
        prompt_string = self.prompt.format(**kwargs)

        tokens["tools"] = 0

        # init tools - first call of the assistant initialize tools
        # It is used to reuse MCP connections between calls and maintain async context.
        try:
            if self.tools and not self._initialized_tools:
                self._initialized_tools = get_and_init_langchain_tools(self.tools, self)
                self._initialized_tools += await get_and_init_mcp_tools(self.tools)
                for tool in self._initialized_tools:
                    self._tools_tokens = 0
                    self._tools_tokens += self._calc_tokens(json.dumps(convert_to_openai_tool(tool)))
                self._tools_number = len(self._initialized_tools) + 1

            agent_executor = create_react_agent(llm, self._initialized_tools, prompt=prompt_string)
        except asyncio.CancelledError:
            self._initialized_tools = []
            logger.info("Assistant init tools was cancelled")
            raise
        except asyncio.TimeoutError:
            self._initialized_tools = []
            logger.info("Assistant init tools was timed out")
            raise

        # Convert input format from kwargs to LangGraph messages format
        messages = []
        if hist:
            messages.extend(hist)
        # Handle multimodal content properly
        formatted_query = self._format_message(query)
        if len(formatted_query) == 1 and formatted_query[0].get("type") == "text":
            # Simple text message
            messages.append(HumanMessage(content=formatted_query[0]["text"]))
        else:
            # Multimodal content - cast to proper type
            messages.append(HumanMessage(content=formatted_query))  # type: ignore

        # Use LangGraph streaming for compatibility with callbacks
        chunks = []
        final_response = ""
        async for chunk in agent_executor.astream({"messages": messages}, config={"callbacks": [langfuse_handler]}):
            chunks.append(chunk)

            if "agent" in chunk:
                for message in chunk["agent"]["messages"]:
                    if isinstance(message, AIMessage):
                        # Handle AI messages (reasoning/tool calls)
                        if message.content:
                            # Convert content to string for token counting and storage
                            tokens["output"] += (
                                len(self.encoding.encode(str(message.content))) + ADDITIONAL_TOKENS_PER_MSG
                            )
                            if isinstance(message.content, str):
                                content_str = message.content
                            elif isinstance(message.content, list):
                                # handle Antropic observation
                                content_text = []
                                for el in message.content:
                                    if el.get("type") == "text":  # type: ignore
                                        content_text.append(el.get("text"))  # type: ignore
                                content_str = "\n".join(content_text)
                            if (
                                self.callbacks["ai_observation"]
                                and hasattr(message, "tool_calls")
                                and message.tool_calls
                            ):
                                # observation to the tool call
                                if ai_db:
                                    ai_db.add_message(LlmMessageType.AI, content_str)
                                self.callbacks["ai_observation"](content_str)
                            else:
                                final_response = content_str

                        # Handle tool calls
                        if hasattr(message, "tool_calls") and message.tool_calls:
                            for tool_call in message.tool_calls:
                                tokens["tools"] += len(self.encoding.encode(str(tool_call))) + ADDITIONAL_TOKENS_PER_MSG
                                msg = f'Invoking Tool: "{tool_call["name"]}" with input "{tool_call["args"]}"'
                                if ai_db:
                                    ai_db.add_message(LlmMessageType.TOOL, msg)
                                if self.callbacks["action"]:
                                    self.callbacks["action"](msg)
            elif "tools" in chunk:
                for message in chunk["tools"]["messages"]:
                    # Handle tool results (ToolMessage)
                    tool_content_str = message.content if isinstance(message.content, str) else str(message.content)
                    tokens["tools"] += len(self.encoding.encode(tool_content_str)) + ADDITIONAL_TOKENS_PER_MSG
                    msg = f"Tool Result: `{tool_content_str}`"
                    if ai_db:
                        ai_db.add_message(LlmMessageType.TOOL, msg)
                    if self.callbacks["observation"]:
                        self.callbacks["observation"](msg)

        # Trigger final output callback
        if self.callbacks["output"]:
            self.callbacks["output"](final_response)

        # corner case: if final_response is empty, use content_str which will be direct result from tool call
        return final_response or tool_content_str
