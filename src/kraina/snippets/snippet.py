"""Base snippet class."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Type, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel

from kraina.libs.langfuse import langfuse_handler
from kraina.libs.llm import FORCE_API_FOR_SNIPPETS, chat_llm, map_model

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

    def invoke(
        self, chat: Union[ChatOpenAI, AzureChatOpenAI], prompt: ChatPromptTemplate, text, **kwargs
    ) -> BaseMessage:
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

        stop_str = ["stop", "end_turn", "stop_sequence"]
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
        """Run the snippet with a user query.

        This function processes the query using a language model,
        applying different settings based on the model type.

        If o-* reasoning model is used, temperature is always 1.
        https://platform.openai.com/docs/guides/reasoning/quickstart

        :param query: Text passed as Human text to LLM chat.
        :param kwargs: Additional key-value pairs to substitute in System prompt.
        :return: The content of the language model's response.
        """
        logger.info(f"{self.name}: query={query[0:80]}..., {kwargs=}")
        llm_kwargs = dict(
            force_api_type=self.force_api or FORCE_API_FOR_SNIPPETS.get("api_type"),
            model=self.model,
            json_mode=self.json_mode,
        )
        if self.model.startswith("o"):  # reasoning models
            llm_kwargs.update(dict(model_kwargs=dict(max_completion_tokens=self.max_tokens), temperature=1))
        else:
            llm_kwargs.update(dict(temperature=self.temperature, max_tokens=self.max_tokens))
        logger.info(f"{self.name}: llm_kwargs={llm_kwargs}, {self.force_api=} {FORCE_API_FOR_SNIPPETS=}")
        chat = chat_llm(**llm_kwargs)
        if self.prompt is None:
            raise ValueError("Snippet prompt cannot be None")
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt),
                ("human", "{text}"),
            ]
        )
        ret = self.invoke(chat, prompt, text=query, date=datetime.now().strftime("%Y-%m-%d"), **kwargs)
        logger.info(f"{self.name}: ret={str(ret)[0:80]}")
        return self.pydantic_output.model_validate_json(ret.content) if self.pydantic_output else ret.content  # type: ignore
