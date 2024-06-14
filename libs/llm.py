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
    map_models = {"gpt-4-turbo": "gpt-4-turbo-128k", "gpt-3.5-turbo": "gpt-35-turbo"}
    return map_models.get(model, model) if isAzureAI() else model


def isAzureAI(force_api_type: str = None) -> bool:
    """
    Is Azure LLM in use?

    :param force_api_type: force openai or azure. If None, check app global settings
    :return:
    """
    if force_api_type == "azure":
        ret = True
    elif force_api_type == "openai":
        ret = False
    else:
        os_env_azure_ok = bool(
            os.environ.get("AZURE_OPENAI_API_KEY")
            and os.environ.get("AZURE_OPENAI_ENDPOINT")
            and os.environ.get("OPENAI_API_VERSION")
        )
        if OVERWRITE_LLM_SETTINGS["api_type"] == "azure" and os_env_azure_ok:
            # Application force to use Azure
            ret = True
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_azure_ok:
            # Application does not force, so check env variable
            # if AZURE env variable exists, select azure
            ret = True
        else:
            ret = False
    return ret


def chat_llm(**kwargs) -> Union[ChatOpenAI, AzureChatOpenAI]:
    """

    :param kwargs:
             force_api_type: azure or openai - force API type
             ... - pass to the chat object
    :return:
    """
    force = kwargs.get("force_api_type", None)
    try:
        kwargs.pop("force_api_type")
    except KeyError:
        pass
    for k, v in OVERWRITE_LLM_SETTINGS.items():
        if k not in ["api_type"] and OVERWRITE_LLM_SETTINGS.get(k, "") != "":
            kwargs[k] = v
    if isAzureAI(force):
        kwargs["model"] = map_model(kwargs["model"])
        return AzureChatOpenAI(**kwargs)
    else:
        return ChatOpenAI(**kwargs)
