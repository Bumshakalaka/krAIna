"""LLM handling."""

import enum
import logging
import os
from pathlib import Path
from typing import Union

import yaml
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock, BedrockEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, AzureChatOpenAI, OpenAIEmbeddings, AzureOpenAIEmbeddings
from langfuse.openai import OpenAI, AzureOpenAI
from langchain_voyageai import VoyageAIEmbeddings
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


class MyBedrockEmbeddings(BedrockEmbeddings):
    def __init__(self, model):
        super().__init__(model_id=model)


class MyChatOllama(ChatOllama):
    def __init__(self, *args, **kwargs):
        kwargs["base_url"] = os.environ.get("OLLAMA_ENDPOINT", None)
        super().__init__(*args, **kwargs)


OVERWRITE_LLM_SETTINGS = {
    "model": "",
    "api_type": "",
    "temperature": "",
    "max_tokens": "",
}


class SUPPORTED_API_TYPE(enum.Enum):
    AZURE = "azure"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AWS = "aws"
    OLLAMA = "ollama"


# TODO: Add validation of model mapping dict
MAP_MODELS = {model: {} for model in SUPPORTED_API_TYPE}


def read_model_settings():
    """
    Read and update model settings from a configuration file.

    This function reads the 'config.yaml' file located in the parent directory
    and updates the `MAP_MODELS` dictionary with the model mapping specified
    in the configuration file.

    :return: None
    :raises FileNotFoundError: If the 'config.yaml' file does not exist.
    """
    if (Path(__file__).parent / "../config.yaml").exists():
        with open(Path(__file__).parent / "../config.yaml") as fd:
            settings = yaml.safe_load(fd.read())
        if settings.get("llm") and settings["llm"].get("map_model"):
            MAP_MODELS.update({SUPPORTED_API_TYPE(k): v for k, v in settings["llm"]["map_model"].items()})
    logger.debug(MAP_MODELS)


read_model_settings()


def overwrite_llm_settings(**new_settings):
    """
    Overwrite LLM chat settings.

    :param new_settings: one of the key=value from OVERWRITE_LLM_SETTINGS
    :return:
    """
    for k, v in new_settings.items():
        if OVERWRITE_LLM_SETTINGS.get(k) is not None:
            OVERWRITE_LLM_SETTINGS[k] = v


def map_model(model: str, api_force: Union[SUPPORTED_API_TYPE, str] = None) -> str:
    """
    Map OpenAI model names to AzureAI

    :param model: openAI model name
    :param api_force:
    :return: AzureAI model name
    """
    if api_force and isinstance(api_force, str):
        api_force = SUPPORTED_API_TYPE(api_force)
    return MAP_MODELS[get_llm_type(api_force)].get(model, model)


def get_llm_type(force_api_type: Union[SUPPORTED_API_TYPE, str] = None) -> SUPPORTED_API_TYPE:
    """
    Get API Type based on force_api_type flag, Chat application settings and env variables.

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
        os_env_anthropic_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
        os_env_aws_ok = bool(os.environ.get("BEDROCK_AWS_SECRET_ACCESS_KEY"))

        if OVERWRITE_LLM_SETTINGS["api_type"]:
            ret = OVERWRITE_LLM_SETTINGS["api_type"]
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_azure_ok:
            # Application does not force, so check env variable
            # if AZURE env variable exists, select azure
            ret = SUPPORTED_API_TYPE.AZURE
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_openai_ok:
            ret = SUPPORTED_API_TYPE.OPENAI
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_anthropic_ok:
            ret = SUPPORTED_API_TYPE.ANTHROPIC
        else:
            ret = SUPPORTED_API_TYPE.AWS
    return SUPPORTED_API_TYPE(ret) if isinstance(ret, str) else ret


def chat_llm(**kwargs) -> Union[ChatOpenAI, AzureChatOpenAI, ChatAnthropic]:
    """

    :param kwargs:
             force_api_type: azure or openai or anthropic - force API type
             json_mode: True if response_format=json_object, False if the text. Default is text
             ... - pass to the chat object
    :return:
    """
    force = kwargs.get("force_api_type", None)
    kwargs.pop("force_api_type", None)
    json_mode = kwargs.get("json_mode", False)
    kwargs.pop("json_mode", None)
    for k, v in OVERWRITE_LLM_SETTINGS.items():
        if k not in ["api_type"] and OVERWRITE_LLM_SETTINGS.get(k, "") != "":
            kwargs[k] = v
    kwargs["model"] = map_model(kwargs["model"], force)
    models = {
        SUPPORTED_API_TYPE.AZURE: AzureChatOpenAI,
        SUPPORTED_API_TYPE.OPENAI: ChatOpenAI,
        SUPPORTED_API_TYPE.ANTHROPIC: ChatAnthropic,
        SUPPORTED_API_TYPE.AWS: ChatBedrock,
        SUPPORTED_API_TYPE.OLLAMA: MyChatOllama,
    }
    if json_mode and get_llm_type(force) not in (
        SUPPORTED_API_TYPE.ANTHROPIC,
        SUPPORTED_API_TYPE.AWS,
        SUPPORTED_API_TYPE.OLLAMA,
    ):
        return models[get_llm_type(force)](**kwargs).bind(response_format={"type": "json_object"})  # noqa
    else:
        return models[get_llm_type(force)](**kwargs)


def embedding(**kwargs) -> Embeddings:
    """
    Create an embedding instance based on specified parameters.

    This function configures and returns an embedding object. It supports different API types
    and adjusts settings based on provided keyword arguments and predefined settings.

    :param kwargs: Arbitrary keyword arguments for embedding configuration.
                   - force_api_type: Optional; forces the use of a specific API type.
                   - model: Required; specifies the model to be used for embeddings.
    :return: An instance of the appropriate embedding class.
    :raises KeyError: If 'model' is not provided in kwargs.
    """
    # TODO: add support for fastembed
    force = kwargs.get("force_api_type", None)
    try:
        kwargs.pop("force_api_type")
    except KeyError:
        pass
    for k, v in OVERWRITE_LLM_SETTINGS.items():
        if k not in ["api_type"] and OVERWRITE_LLM_SETTINGS.get(k, "") != "":
            kwargs[k] = v
    kwargs["model"] = map_model(kwargs["model"], force)
    embeddings = {
        SUPPORTED_API_TYPE.AZURE: AzureOpenAIEmbeddings,
        SUPPORTED_API_TYPE.OPENAI: OpenAIEmbeddings,
        SUPPORTED_API_TYPE.ANTHROPIC: VoyageAIEmbeddings,
        SUPPORTED_API_TYPE.AWS: MyBedrockEmbeddings,
    }
    return embeddings[get_llm_type(force)](**kwargs)


def llm_client(**kwargs) -> Union[OpenAI, AzureOpenAI]:
    """

    :param kwargs:
             force_api_type: azure or openai or anthropic - force API type
             ... - pass to the chat object
    :return:
    """
    force: Union[str, None] = kwargs.get("force_api_type", None)
    try:
        kwargs.pop("force_api_type")
    except KeyError:
        pass
    for k, v in OVERWRITE_LLM_SETTINGS.items():
        if k not in ["api_type"] and OVERWRITE_LLM_SETTINGS.get(k, "") != "":
            kwargs[k] = v
    llm = {
        SUPPORTED_API_TYPE.AZURE: AzureOpenAI,
        SUPPORTED_API_TYPE.OPENAI: OpenAI,
    }
    return llm[get_llm_type(force)]()
