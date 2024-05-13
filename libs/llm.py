"""LLM handling."""
import os
from typing import Union

from langchain_openai import ChatOpenAI, AzureChatOpenAI


def chat_llm(*args, **kwargs) -> Union[ChatOpenAI, AzureChatOpenAI]:
    """
    Select and return on of the LLM to use.

    If environment variables AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT exist, initialize AzureChatOpenAI.
    Otherwise, initialize ChatOpenAI.

    """
    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get(
        "AZURE_OPENAI_ENDPOINT"
    ):
        return AzureChatOpenAI(*args, **kwargs)
    else:
        return ChatOpenAI(*args, **kwargs)
