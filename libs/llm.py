"""LLM handling."""
import os
from typing import Union

from langchain_openai import ChatOpenAI, AzureChatOpenAI


def map_model(model: str) -> str:
    """
    Map OpenAI model names to AzureAI

    :param model: openAI model name
    :return: AzureAI model name
    """
    map_models = {"gpt-4-turbo": "gpt-4-turbo-128k", "gpt-3.5-turbo": "gpt-35-turbo"}
    if isAzureAI():
        return map_models.get(model, model)
    else:
        return model


def isAzureAI() -> bool:
    """Is Azure LLM in use?"""
    return bool(
        os.environ.get("AZURE_OPENAI_API_KEY")
        and os.environ.get("AZURE_OPENAI_ENDPOINT")
    )


def chat_llm(**kwargs) -> Union[ChatOpenAI, AzureChatOpenAI]:
    """
    Select and return on of the LLM to use.

    If environment variables AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT exist, initialize AzureChatOpenAI.
    Otherwise, initialize ChatOpenAI.

    """
    if isAzureAI():
        kwargs["model"] = map_model(kwargs["model"])
        return AzureChatOpenAI(**kwargs)
    else:
        return ChatOpenAI(**kwargs)
