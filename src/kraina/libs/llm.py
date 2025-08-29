"""LLM handling module for Kraina.

This module provides a unified interface for working with various Large Language Model (LLM) APIs
including OpenAI, Azure OpenAI, Anthropic, AWS Bedrock, Ollama, and Google Generative AI.
It handles model mapping, API type selection, and provides functions for creating chat models,
embedding models, and direct LLM clients.

The module supports:
- Multiple API providers (OpenAI, Azure, Anthropic, AWS, Ollama, Google)
- Model name mapping and aliases
- Environment-based API type selection
- Override settings for LLM parameters
- JSON mode support for compatible APIs
"""

import enum
import logging
import os
from typing import Any, Optional, Union

import yaml
from jsonschema import ValidationError
from langchain_anthropic import ChatAnthropic
from langchain_aws import BedrockEmbeddings, ChatBedrock
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings
from langchain_voyageai import VoyageAIEmbeddings
from openai import AzureOpenAI, OpenAI
from pydantic import Field

from kraina.libs.paths import CONFIG_FILE, config_file_validation

logger = logging.getLogger(__name__)


class MyChatOpenAI(ChatOpenAI):
    """Custom Chat OpenAI class with overwrite temperature for o-series models."""

    def _get_request_payload(
        self,
        input_,
        *,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if self.model_name and (self.model_name.startswith("o") or self.model_name.startswith("gpt-5")):
            # o-series models require temperature=1.0, overwrite it if it is set
            if "temperature" in payload:
                payload["temperature"] = 1.0
        return payload


class MyAzureChatOpenAI(AzureChatOpenAI):
    """Custom Azure Chat OpenAI class with max_tokens alias and overwrite temperature for o-series models."""

    max_tokens: Optional[int] = Field(default=None, alias="max_completion_tokens")
    """Maximum number of tokens to generate."""

    @property
    def _default_params(self) -> dict[str, Any]:
        """Get the default parameters for calling OpenAI API."""
        params = super()._default_params
        if "max_tokens" in params:
            params["max_completion_tokens"] = params.pop("max_tokens")

        return params

    def _get_request_payload(
        self,
        input_,
        *,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        # max_tokens was deprecated in favor of max_completion_tokens
        # in September 2024 release
        if "max_tokens" in payload:
            payload["max_completion_tokens"] = payload.pop("max_tokens")

        # Mutate system message role to "developer" for o-series models
        # Mutate temperature to 1.0 for o-series models
        if self.model_name and (self.model_name.startswith("o") or self.model_name.startswith("gpt-5")):
            # o-series models require temperature=1.0, overwrite it if it is set
            if "temperature" in payload:
                payload["temperature"] = 1.0
            for message in payload.get("messages", []):
                if message["role"] == "system":
                    message["role"] = "developer"
        return payload


class MyBedrockEmbeddings(BedrockEmbeddings):
    """Custom Bedrock embeddings class with simplified initialization."""

    def __init__(self, model: str):
        """Initialize Bedrock embeddings with model ID.

        Args:
            model: The model ID to use for embeddings

        """
        super().__init__(model_id=model)


class MyChatOllama(ChatOllama):
    """Custom Ollama chat class with environment-based endpoint configuration."""

    def __init__(self, *args, **kwargs):
        """Initialize Ollama chat with optional base URL from environment.

        Args:
            *args: Positional arguments passed to parent class
            **kwargs: Keyword arguments passed to parent class

        """
        kwargs["base_url"] = os.environ.get("OLLAMA_ENDPOINT", None)
        super().__init__(*args, **kwargs)


OVERWRITE_LLM_SETTINGS = {
    "model": "",
    "api_type": "",
    "temperature": "",
    "max_tokens": "",
}


class SUPPORTED_API_TYPE(enum.Enum):
    """Enumeration of supported API types for LLM providers."""

    AZURE = "azure"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AWS = "aws"
    OLLAMA = "ollama"
    GOOGLE = "google"


# TODO: Add validation of model mapping dict
MAP_MODELS = {model: {} for model in SUPPORTED_API_TYPE}
FORCE_API_FOR_SNIPPETS = {}


def read_model_settings() -> bool:
    """Read and update model settings from a configuration file.

    This function reads the 'config.yaml' file located in the parent directory
    and updates the `MAP_MODELS` dictionary with the model mapping specified
    in the configuration file.

    Returns:
        bool: True if config.yaml is valid and read successfully, False otherwise

    Raises:
        FileNotFoundError: If the 'config.yaml' file does not exist

    """
    try:
        config_file_validation()
    except ValidationError as e:
        logger.exception(e)
        return False
    else:
        with open(CONFIG_FILE) as fd:
            settings = yaml.safe_load(fd.read())
            if settings.get("llm") and settings["llm"].get("map_model"):
                MAP_MODELS.update({SUPPORTED_API_TYPE(k): v for k, v in settings["llm"]["map_model"].items()})
            if settings.get("llm") and settings["llm"].get("force_api_for_snippets"):
                FORCE_API_FOR_SNIPPETS.update({"api_type": settings["llm"]["force_api_for_snippets"]})
        return True


read_model_settings()


def get_only_aliases() -> list[str]:
    """Return all one-letter model aliases from MAP_MODELS for all SUPPORTED_API_TYPE.

    Returns:
        list[str]: Sorted list of single-letter model aliases

    """
    aliases = set()
    for _, models in MAP_MODELS.items():
        for k in models:
            if isinstance(k, str) and len(k) == 1 and k.isalpha():
                aliases.add(k)
    return sorted(aliases)


def overwrite_llm_settings(**new_settings) -> None:
    """Overwrite LLM chat settings with new values.

    Args:
        **new_settings: Key-value pairs from OVERWRITE_LLM_SETTINGS to update

    """
    for k, v in new_settings.items():
        if OVERWRITE_LLM_SETTINGS.get(k) is not None:
            OVERWRITE_LLM_SETTINGS[k] = v


def map_model(model: str, api_force: Optional[Union[SUPPORTED_API_TYPE, str]] = None) -> str:
    """Map model names based on API type and configuration.

    Maps OpenAI model names to their corresponding names in other APIs (e.g., Azure AI)
    based on the configuration in MAP_MODELS.

    Args:
        model: The model name to map
        api_force: Optional API type to force mapping for a specific provider

    Returns:
        str: The mapped model name, or original name if no mapping exists

    """
    if api_force and isinstance(api_force, str):
        api_force = SUPPORTED_API_TYPE(api_force)
    return MAP_MODELS[get_llm_type(api_force)].get(model, model)


def get_llm_type(
    force_api_type: Optional[Union[SUPPORTED_API_TYPE, str]] = None,
) -> SUPPORTED_API_TYPE:
    """Get API Type based on force_api_type flag, Chat application settings and env variables.

    Determines which API type to use based on:
    1. Forced API type parameter
    2. Application global settings
    3. Environment variables
    4. Default fallback to AWS

    Args:
        force_api_type: Optional API type to force (azure, openai, anthropic, etc.)

    Returns:
        SUPPORTED_API_TYPE: The determined API type to use

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
        # os_env_aws_ok = bool(os.environ.get("BEDROCK_AWS_SECRET_ACCESS_KEY"))
        os_env_google_ok = bool(os.environ.get("GOOGLE_API_KEY"))

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
        elif OVERWRITE_LLM_SETTINGS["api_type"] == "" and os_env_google_ok:
            ret = SUPPORTED_API_TYPE.GOOGLE
        else:
            ret = SUPPORTED_API_TYPE.AWS
    return SUPPORTED_API_TYPE(ret) if isinstance(ret, str) else ret


def chat_llm(
    **kwargs,
) -> Union[MyChatOpenAI, MyAzureChatOpenAI, ChatAnthropic, ChatBedrock, MyChatOllama, ChatGoogleGenerativeAI]:
    """Create a chat LLM instance based on configuration and parameters.

    Creates and configures a chat model instance for the appropriate API provider.
    Supports JSON mode for compatible APIs and applies global override settings.

    Args:
        **kwargs: Configuration parameters for the chat model
            - force_api_type: Optional API type to force (azure, openai, anthropic, etc.)
            - json_mode: If True, sets response_format=json_object (default: False)
            - model: Required model name
            - temperature: Optional temperature setting
            - max_tokens: Optional maximum tokens setting
            - Additional parameters passed to the chat model constructor

    Returns:
        Union[ChatOpenAI, AzureChatOpenAI, ChatAnthropic, ChatBedrock, MyChatOllama, ChatGoogleGenerativeAI]:
            Configured chat model instance

    Raises:
        KeyError: If 'model' is not provided in kwargs

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
        SUPPORTED_API_TYPE.AZURE: MyAzureChatOpenAI,
        SUPPORTED_API_TYPE.OPENAI: MyChatOpenAI,
        SUPPORTED_API_TYPE.ANTHROPIC: ChatAnthropic,
        SUPPORTED_API_TYPE.AWS: ChatBedrock,
        SUPPORTED_API_TYPE.OLLAMA: MyChatOllama,
        SUPPORTED_API_TYPE.GOOGLE: ChatGoogleGenerativeAI,
    }
    if json_mode and get_llm_type(force) not in (
        SUPPORTED_API_TYPE.ANTHROPIC,
        SUPPORTED_API_TYPE.AWS,
        SUPPORTED_API_TYPE.OLLAMA,
        SUPPORTED_API_TYPE.GOOGLE,
    ):
        return models[get_llm_type(force)](**kwargs).bind(response_format={"type": "json_object"})  # noqa
    else:
        return models[get_llm_type(force)](**kwargs)


def embedding(**kwargs) -> Embeddings:
    """Create an embedding instance based on specified parameters.

    This function configures and returns an embedding object. It supports different API types
    and adjusts settings based on provided keyword arguments and predefined settings.

    Args:
        **kwargs: Configuration parameters for the embedding model
            - force_api_type: Optional API type to force
            - model: Required model name for embeddings
            - Additional parameters passed to the embedding model constructor

    Returns:
        Embeddings: Configured embedding model instance

    Raises:
        KeyError: If 'model' is not provided in kwargs

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
        SUPPORTED_API_TYPE.GOOGLE: GoogleGenerativeAIEmbeddings,
    }
    return embeddings[get_llm_type(force)](**kwargs)


def llm_client(**kwargs) -> Union[OpenAI, AzureOpenAI, GoogleGenerativeAI]:
    """Create a direct LLM client instance.

    Creates a direct client for the appropriate API provider, bypassing LangChain.
    Useful for direct API calls and fine-grained control.

    Args:
        **kwargs: Configuration parameters for the LLM client
            - force_api_type: Optional API type to force
            - Additional parameters passed to the client constructor

    Returns:
        Union[OpenAI, AzureOpenAI, GoogleGenerativeAI]: Configured LLM client instance

    """
    force: Optional[Union[str, SUPPORTED_API_TYPE]] = kwargs.get("force_api_type", None)
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
        SUPPORTED_API_TYPE.GOOGLE: GoogleGenerativeAI,
    }
    return llm[get_llm_type(force)]()
