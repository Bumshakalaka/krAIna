"""Base snippet class."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Union, List

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, AzureChatOpenAI

from libs.langfuse import langfuse_handler
from libs.llm import chat_llm, map_model

logger = logging.getLogger(__name__)

SPECIALIZED_SNIPPETS = {}


@dataclass(eq=False)
class BaseSnippet:
    """
    Base class for all snippets.
    """

    name: str = ""
    """Snippet name"""
    prompt: str = None
    """Snippet system prompt"""
    _model: str = "gpt-3.5-turbo"
    """Snippet LLM model"""
    temperature: float = 0.5
    """Snippet temperature"""
    max_tokens: int = 512
    """Max token response"""
    force_api: str = None  # azure, openai, anthropic
    """Force to use azure or openai or anthropic"""
    contexts: List[str] = None
    """List of additional contexts to be added to system prompt"""
    path: Path = None
    """Path to the snippet folder."""

    def __init_subclass__(cls, **kwargs):
        """
        Automatically add all subclasses of this class to `SPECIALIZED_SNIPPETS` dict.

        Add only class which names do not start with _
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            SPECIALIZED_SNIPPETS[cls.__name__] = cls

    @property
    def model(self) -> str:
        return map_model(self._model, self.force_api)

    @model.setter
    def model(self, value: str):
        self._model = value

    def invoke(
        self, chat: Union[ChatOpenAI, AzureChatOpenAI], prompt: ChatPromptTemplate, text, **kwargs
    ) -> BaseMessage:
        """
        LLM request for completions with support to continue generation when max_tokens response has been reached.

        :param chat: LLM Chat object
        :param prompt: LLM prompt to use
        :param text: query text
        :param kwargs: additonal args
        :return:
        """
        ret = chat.invoke(
            prompt.format_prompt(text=text, **kwargs), config={"callbacks": [langfuse_handler(["snippet", self.name])]}
        )
        finish_reason = "finish_reason"
        stop_str = ["stop"]
        if isinstance(chat, ChatAnthropic):
            finish_reason = "stop_reason"
            stop_str = ["end_turn", "stop_sequence"]
        if ret.response_metadata[finish_reason] in stop_str:
            # complete response received
            return ret
        else:
            # max tokens reached. Consider setting larger max_tokens
            while ret.response_metadata[finish_reason] not in stop_str:
                # ask for the next chunk
                prompt.append(ret)  # add the previous chunk to the conversation
                prompt.append(HumanMessage("The response is not complete, continue"))  # ask for more
                ret = chat.invoke(
                    prompt.format_prompt(text=text, **kwargs),
                    config={"callbacks": [langfuse_handler(["snippet", self.name])]},
                )  # send request to LLM
                if ret.content.strip() == "":
                    raise AttributeError(
                        f"'max_tokens' {self.max_tokens} is too low to get response, consider increase it"
                    )
            # now wwe have all chunks. Concatenate all AI responses and return them together with last response from LLM
            ret.content = "".join([ai_msg.content for ai_msg in prompt.messages if isinstance(ai_msg, AIMessage)])
            return ret

    def run(self, query: str, /, **kwargs) -> str:
        """
        Run the snippet with a user query.

        This function processes the query using a language model,
        applying different settings based on the model type.

        If o1-* reasoning model is used, the system prompt becomes user prompt and temperature is always 1.
        https://platform.openai.com/docs/guides/reasoning/quickstart

        :param query: Text passed as Human text to LLM chat.
        :param kwargs: Additional key-value pairs to substitute in System prompt.
        :return: The content of the language model's response.
        """
        logger.info(f"{self.name}: query={query[0:80]}..., {kwargs=}")
        llm_kwargs = dict(force_api_type=self.force_api, model=self.model)
        if self.model.startswith("o1"):  # reasoning models
            llm_kwargs.update(dict(max_completion_tokens=self.max_tokens, temperature=1))
            system_role = "human"
        else:
            llm_kwargs.update(dict(temperature=self.temperature, max_tokens=self.max_tokens))
            system_role = "system"
        chat = chat_llm(**llm_kwargs)
        prompt = ChatPromptTemplate.from_messages(
            [
                (system_role, self.prompt),
                ("human", "{text}"),
            ]
        )
        ret = self.invoke(chat, prompt, text=query, date=datetime.now().strftime("%Y-%m-%d"), **kwargs)
        logger.info(f"{self.name}: ret={str(ret)[0:80]}")
        return ret.content
