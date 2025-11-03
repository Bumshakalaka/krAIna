"""Base snippet class."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from kraina.libs.langfuse import langfuse_handler
from kraina.libs.llm import FORCE_API_FOR_SNIPPETS, chat_llm, map_model
from kraina.libs.utils import IMAGE_DATA_URL_MARKDOWN_RE
from kraina.tools.base import get_and_init_langchain_tools, get_and_init_mcp_tools

logger = logging.getLogger(__name__)

SPECIALIZED_SNIPPETS = {}


@dataclass(eq=False)
class BaseSnippet:
    """Base class for all snippets."""

    name: str = ""
    """Snippet name"""
    prompt: Optional[str] = None
    """Snippet system prompt"""
    _model: str = "gpt-3.5-turbo"
    """Snippet LLM model"""
    temperature: float = 0.5
    """Snippet temperature"""
    max_tokens: int = 512
    """Max token response"""
    force_api: Optional[str] = None  # azure, openai, anthropic
    """Force to use azure or openai or anthropic"""
    contexts: Optional[List[str]] = None
    """List of additional contexts to be added to system prompt"""
    path: Optional[Path] = None
    """Path to the snippet folder."""
    json_mode: bool = False
    """Force LLM to output in json_object format"""
    pydantic_output: Optional[Type[BaseModel]] = None
    """Serialize JSON output into Pydantic model. The best is to use with json_mode"""
    tools: Optional[List[str]] = None
    """Tools to use when running snippet via LangGraph agent"""
    _initialized_tools: List[BaseTool] = field(default_factory=list, init=False, repr=False)
    """Internal cache of initialized tools reused across snippet runs"""

    def __init_subclass__(cls, **kwargs):
        """Automatically add all subclasses of this class to `SPECIALIZED_SNIPPETS` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_SNIPPETS[cls.__name__] = cls

    @property
    def model(self) -> str:
        """Get the mapped model name based on force_api setting.

        :return: The mapped model name.
        """
        return map_model(self._model, self.force_api or FORCE_API_FOR_SNIPPETS.get("api_type"))

    @model.setter
    def model(self, value: str):
        self._model = value

    def invoke(self, chat, prompt: ChatPromptTemplate, text, **kwargs) -> BaseMessage:
        """LLM request for completions with support to continue generation when max_tokens response has been reached.

        :param chat: LLM Chat object
        :param prompt: LLM prompt to use
        :param text: query text
        :param kwargs: additonal args
        :return:
        """
        ret = chat.invoke(prompt.format_prompt(text=text, **kwargs), config={"callbacks": [langfuse_handler]})
        finish_reason = None
        last_exception = None
        for reason in ["finish_reason", "stop_reason", "done_reason"]:
            try:
                finish_reason = ret.response_metadata[reason]
                break
            except KeyError as e:
                last_exception = e
                continue
        else:
            if last_exception is not None:
                raise last_exception
            raise KeyError("No finish reason found in response metadata")

        stop_str = ["stop", "end_turn", "stop_sequence", "done"]
        if finish_reason in stop_str:
            # complete response received
            return ret
        else:
            # max tokens reached. Consider setting larger max_tokens
            while finish_reason not in stop_str:
                # ask for the next chunk
                prompt.append(ret)  # add the previous chunk to the conversation
                prompt.append(HumanMessage("The response is not complete, continue"))  # ask for more
                ret = chat.invoke(
                    prompt.format_prompt(text=text, **kwargs),
                    config={"callbacks": [langfuse_handler]},
                )  # send request to LLM
                if not ret.content or (isinstance(ret.content, str) and ret.content.strip() == ""):
                    raise AttributeError(
                        f"'max_tokens' {self.max_tokens} is too low to get response, consider increase it"
                    )
            # now wwe have all chunks. Concatenate all AI responses and return them together with last response from LLM
            ret.content = "".join([ai_msg.content for ai_msg in prompt.messages if isinstance(ai_msg, AIMessage)])  # type: ignore
            return ret

    def run(self, query: str, /, **kwargs) -> str | Type[BaseModel]:
        """Run the snippet with a user query."""
        logger.info(f"{self.name}: query={query[0:80]}..., {kwargs=}")
        llm_kwargs = self._build_llm_kwargs()
        logger.info(f"{self.name}: llm_kwargs={llm_kwargs}, {self.force_api=} {FORCE_API_FOR_SNIPPETS=}")

        if self.tools:
            raw_response = self._run_with_tools_sync(query, llm_kwargs, **kwargs)
        else:
            raw_response = self._run_simple(query, llm_kwargs, **kwargs)

        logger.info(f"{self.name}: ret={raw_response[0:80] if raw_response else raw_response}")
        return self._finalize_response(raw_response)

    def _build_llm_kwargs(self) -> Dict[str, Any]:
        """Create kwargs for chat LLM client respecting snippet configuration."""
        return dict(
            force_api_type=self.force_api or FORCE_API_FOR_SNIPPETS.get("api_type"),
            model=self.model,
            json_mode=self.json_mode,
            temperature=float(self.temperature),
            max_tokens=float(self.max_tokens),
        )

    def _run_simple(self, query: str, llm_kwargs: Dict[str, Any], **kwargs) -> str:
        """Execute snippet without tools using direct LLM invocation."""
        if self.prompt is None:
            raise ValueError("Snippet prompt cannot be None")

        chat = chat_llm(**llm_kwargs)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                ("human", "{text}"),
            ]
        )
        response = self.invoke(
            chat,
            prompt,
            text=query,
            date=datetime.now().strftime("%Y-%m-%d"),
            **kwargs,
        )
        return self._normalize_response_content(response.content)

    def _run_with_tools_sync(self, query: str, llm_kwargs: Dict[str, Any], **kwargs) -> str:
        """Execute snippet leveraging LangChain/MCP tools via LangGraph agent."""
        try:
            asyncio.get_running_loop()
            raise RuntimeError("Cannot call sync run() from async context. Use asynchronous execution instead.")
        except RuntimeError as exc:
            if "no running event loop" not in str(exc).lower():
                raise

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return asyncio.run(self._arun_with_tools(query, llm_kwargs, **kwargs))
            return loop.run_until_complete(self._arun_with_tools(query, llm_kwargs, **kwargs))
        except RuntimeError:
            return asyncio.run(self._arun_with_tools(query, llm_kwargs, **kwargs))

    async def _arun_with_tools(self, query: str, llm_kwargs: Dict[str, Any], **kwargs) -> str:
        """Async execution path for tool-enabled snippets."""
        if self.prompt is None:
            raise ValueError("Snippet prompt cannot be None")

        llm = chat_llm(**llm_kwargs)
        prompt_kwargs = dict(kwargs)
        prompt_kwargs.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
        prompt_kwargs.setdefault("text", query)
        prompt_string = self.prompt.format(**prompt_kwargs)

        if self.tools is not None and not self._initialized_tools:
            try:
                langchain_tools = get_and_init_langchain_tools(self.tools, self)
                mcp_tools = await get_and_init_mcp_tools(self.tools)
                self._initialized_tools.extend([*langchain_tools, *mcp_tools])
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                self._initialized_tools = []
                raise

        agent_executor = create_react_agent(llm, self._initialized_tools, prompt=prompt_string)

        formatted_query = self._format_message(query)
        if len(formatted_query) == 1 and formatted_query[0].get("type") == "text":
            human_message = HumanMessage(content=formatted_query[0]["text"])
        else:
            human_message = HumanMessage(content=formatted_query)  # type: ignore[arg-type]

        result = await agent_executor.ainvoke(
            {"messages": [human_message]},
            config={"callbacks": [langfuse_handler]},
        )

        if isinstance(result, dict):
            messages = result.get("messages", [])
        elif isinstance(result, BaseMessage):
            messages = [result]
        else:
            raise TypeError(f"Unexpected agent response type: {type(result)}")

        final_message = next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)
        if final_message is None:
            raise RuntimeError("Agent execution produced no AI response")

        return self._normalize_response_content(final_message.content)

    def _normalize_response_content(self, content: Any) -> str:
        """Convert LLM content payload into plain text."""
        if isinstance(content, str):
            value = content
        elif isinstance(content, list):
            fragments = []
            for element in content:
                if isinstance(element, dict) and element.get("type") == "text":
                    text_value = element.get("text", "")
                    if text_value:
                        fragments.append(text_value)
            value = "\n".join(fragments)
        else:
            value = str(content)

        normalized = value.strip()
        if not normalized:
            logger.debug(f"{self.name}: Empty response content received from LLM")
        return normalized

    def _finalize_response(self, response: str) -> str | Type[BaseModel]:
        """Apply optional Pydantic conversion to raw response."""
        if self.pydantic_output:
            return self.pydantic_output.model_validate_json(response)  # type: ignore
        return response

    @staticmethod
    def _format_message(msg: str) -> List[Dict[str, Any]]:
        """Split message into text and image segments for multimodal support."""
        if not msg:
            return [dict(type="text", text=".")]

        content: List[Dict[str, Any]] = []
        start_idx = 0
        for match in IMAGE_DATA_URL_MARKDOWN_RE.finditer(msg):
            image_start = match.start(0)
            if image_start > start_idx:
                content.append(dict(type="text", text=msg[start_idx:image_start]))
            start_idx = match.end(0)
            content.append(dict(type="image_url", image_url=dict(url=match.group("img_data"))))

        if msg[start_idx:]:
            content.append(dict(type="text", text=msg[start_idx:]))

        return content
