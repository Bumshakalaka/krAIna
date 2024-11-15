import functools
from pathlib import Path
from typing import Dict

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool

from libs.llm import llm_client, map_model

load_dotenv(find_dotenv())


class AudioToTextInput(BaseModel):
    file_path: str = Field(description="local audio file to transcript")


def audio_to_text(model: str, force_api: str, file_path: str):
    """
    Convert audio file to text using a specified model and API.

    This function utilizes a language model client to transcribe audio content
    from a file specified by the file path.

    :param model: The model to be used for transcription.
    :param force_api: The API type to force the client to use.
    :param file_path: The path to the audio file to be transcribed.
    :return: The transcribed text from the audio file.
    """
    if not Path(file_path).exists():
        return f"'{file_path}' file not exists"
    client = llm_client(force_api_type=force_api)
    with open(file_path, "rb") as fd:
        response = client.audio.transcriptions.create(
            model=model,
            file=fd,
        )
    return response.text


def init_audio_to_text(tool_setting: Dict) -> BaseTool:
    """
    Initialize the audio-to-text tool with provided settings.

    This function sets up an audio-to-text tool by configuring it
    with the model and API settings from the tool settings dictionary.

    :param tool_setting: A dictionary containing tool configuration settings.
    :return: An instance of a BaseTool configured for audio-to-text transcription.
    """
    return StructuredTool.from_function(
        func=functools.partial(
            audio_to_text,
            map_model(tool_setting.get("model", "whisper-1"), tool_setting["assistant"].force_api),
            tool_setting["assistant"].force_api,
        ),
        name="audio-to-text",
        description="A wrapper around audio-to-text API. Useful when you need to transcript audio files",
        args_schema=AudioToTextInput,
        return_direct=True,
    )
