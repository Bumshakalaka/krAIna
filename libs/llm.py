"""LLM handling."""
import logging
import os
from typing import Union

from langchain_openai import ChatOpenAI, AzureChatOpenAI

logger = logging.getLogger(__name__)

OVERWRITE_LLM_SETTINGS = {
    "model": "",
    "api_type": "",
    "temperature": "",
    "max_tokens": "",
}


def overwrite_llm_settings(**new_settings):
    """
    Overwrite LLM chat settings.

    :param new_settings: one of the key=value from OVERWRITE_LLM_SETTINGS
    :return:
    """
    for k, v in new_settings.items():
        if OVERWRITE_LLM_SETTINGS.get(k) is not None:
            OVERWRITE_LLM_SETTINGS[k] = v


def map_model(model: str) -> str:
    """
    Map OpenAI model names to AzureAI

    :param model: openAI model name
    :return: AzureAI model name
    """
    map_models = {"gpt-4-turbo": "gpt-4-turbo-128k", "gpt-3.5-turbo": "gpt-35-turbo", "gpt-4o": ""}
    return map_models.get(model, model) if isAzureAI() else model


def isAzureAI() -> bool:
    """Is Azure LLM in use?"""
    azure = True if OVERWRITE_LLM_SETTINGS["api_type"] == "azure" else False
    return True if azure else bool(os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"))


def chat_llm(**kwargs) -> Union[ChatOpenAI, AzureChatOpenAI]:
    """
    Select and return on of the LLM to use.

    If environment variables AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT exist, initialize AzureChatOpenAI.
    Otherwise, initialize ChatOpenAI.

    """
    for k, v in OVERWRITE_LLM_SETTINGS.items():
        if k not in ["api_type"] and OVERWRITE_LLM_SETTINGS.get(k, "") != "":
            kwargs[k] = v
    if isAzureAI():
        kwargs["model"] = map_model(kwargs["model"])
        return AzureChatOpenAI(**kwargs)
    else:
        return ChatOpenAI(**kwargs)
