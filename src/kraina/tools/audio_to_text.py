import tempfile
from pathlib import Path
from typing import Dict

import requests
from dotenv import find_dotenv, load_dotenv
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from kraina.libs.llm import llm_client, map_model

load_dotenv(find_dotenv())


class AudioToTextInput(BaseModel):
    uri: str = Field(description="Audio file to transcript. Local or from URL")


def audio_to_text(uri: str, model: str = "whisper-1", force_api: str = None):
    """Convert audio file to text using a specified model.

    This function checks for the existence of the audio file, then uses a language model client
    to transcribe the audio file into text.

    :param uri: Path to the audio file (local or url) to be transcribed.
    :param model: The model to be used for transcription, default is 'whisper-1'.
    :param force_api: Optional parameter to specify a particular API type. openai, azure
    :return: Transcribed text from the audio file or an error message if the file does not exist.
    :raises FileNotFoundError: If the specified audio file does not exist.
    """
    if uri.startswith("http"):
        with tempfile.NamedTemporaryFile(delete=False, mode="wb", suffix="." + uri.split(".")[-1]) as fd:
            fd.write(requests.get(uri).content)
        uri = fd.name
    if not Path(uri).exists():
        return f"'{uri}' file not exists"
    client = llm_client(force_api_type=force_api)
    with open(uri, "rb") as fd:
        response = client.audio.transcriptions.create(
            model=model,
            file=fd,
        )
    return response.text


def init_audio_to_text(tool_setting: Dict) -> BaseTool:
    """Initialize the audio-to-text tool with provided settings.

    This function sets up an audio-to-text tool by configuring it
    with the model and API settings from the tool settings dictionary.

    :param tool_setting: A dictionary containing tool configuration settings.
    :return: An instance of a BaseTool configured for audio-to-text transcription.
    """
    return StructuredTool.from_function(
        func=(lambda model, force_api: lambda uri: audio_to_text(uri, model, force_api))(
            model=map_model(tool_setting.get("model", "whisper-1"), tool_setting["assistant"].force_api),
            force_api=tool_setting["assistant"].force_api,
        ),
        name="audio-to-text",
        description="A wrapper around audio-to-text API. Useful when you need to transcript audio files",
        args_schema=AudioToTextInput,
        return_direct=False,
    )
