"""LLM handling."""
import logging
import os
from pathlib import Path
from typing import Union

import yaml
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI, AzureChatOpenAI

logger = logging.getLogger(__name__)

OVERWRITE_LLM_SETTINGS = {
    "model": "",
    "api_type": "",
    "temperature": "",
    "max_tokens": "",
}

# TODO: Add validation of model mapping dict
MAP_MODELS = {
    "azure": {},
    "openai": {},
    "anthropic": {},
}
with open(Path(__file__).parent / "../config.yaml") as fd:
    settings = yaml.safe_load(fd.read())
if settings.get("llm") and settings["llm"].get("map_model"):
    MAP_MODELS.update(settings["llm"]["map_model"])
logger.debug(MAP_MODELS)


def overwrite_llm_settings(**new_settings):
    """
    Overwrite LLM chat settings.

    :param new_settings: one of the key=value from OVERWRITE_LLM_SETTINGS
    :return:
    """
    for k, v in new_settings.items():
        if OVERWRITE_LLM_SETTINGS.get(k) is not None:
            OVERWRITE_LLM_SETTINGS[k] = v


def map_model(model: str, api_force: str = None) -> str:
    """
    Map OpenAI model names to AzureAI

    :param model: openAI model name
    :param api_force:
    :return: AzureAI model name
    """
    return MAP_MODELS[get_llm_type(api_force)].get(model, model)


def get_llm_type(force_api_type: str = None) -> str:
    """
    Is Azure LLM in use?

    :param force_api_type: force openai or azure or anthropic. If None, check app global settings
    :return:
    """
    if force_api_type:
        ret = force_api_type
    else:
        os_env_azure_ok = bool(
            os.environ.get("AZURE_OPENAI_API_KEY")
            and os.environ.get("AZURE_OPENAI_ENDPOINT")
            and os.environ.get("OPENAI_API_VERSION")
        )
        os_env_openai_ok = bool(os.environ.get("OPENAI_API_KEY"))

        if OVERWRITE_LLM_SETTINGS["api_type"]:
            ret = OVERWRITE_LLM_SETTINGS["api_type"]
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_azure_ok:
            # Application does not force, so check env variable
            # if AZURE env variable exists, select azure
            ret = "azure"
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_openai_ok:
            ret = "openai"
        else:
            ret = "anthropic"
    return ret


def chat_llm(**kwargs) -> Union[ChatOpenAI, AzureChatOpenAI, ChatAnthropic]:
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
    kwargs["model"] = map_model(kwargs["model"], force)
    models = {"azure": AzureChatOpenAI(**kwargs), "openai": ChatOpenAI(**kwargs), "anthropic": ChatAnthropic(**kwargs)}
    return models[get_llm_type(force)]


def chat_llm_response(ret):
    # TODO: depends on chat, return proper structure
    pass
