"""Text to text processing tool.

This module provides functionality to read and process text content from
local files or URLs, making it available for further processing.
"""

from pathlib import Path
from typing import Dict

import requests
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field


class TextToTextInput(BaseModel):
    """Input schema for text to text processing.

    Defines the required input parameters for reading text content.
    """

    uri: str = Field(description="Read text content. Content can be local text file or URL from where content is fetch")


def text_to_text(uri: str):
    """Retrieve text from a URL or a local file.

    If the URI starts with 'http', it fetches the content from the URL.
    Otherwise, it reads the content from a local file.

    :param uri: A string representing a URL or a file path.
    :return: The text content from the URL or file, or an error message if the file does not exist.
    :raises FileNotFoundError: If the specified file path does not exist.
    """
    if uri.startswith("http"):
        return requests.get(uri).content.decode("utf-8")
    else:
        if not Path(uri).exists():
            return f"'{uri}' file not exists"
        with open(uri, "r") as fd:
            return fd.read()


def init_text_to_text(tool_setting: Dict) -> BaseTool:  # noqa: ARG001
    """Initialize the text-to-text tool with the given settings.

    This function sets up a StructuredTool using the text_to_text function
    and the specified tool settings.

    :param tool_setting: A dictionary containing tool configuration settings.
    :return: An instance of BaseTool configured for text-to-text operations.
    """
    return StructuredTool.from_function(
        func=text_to_text,
        name="text-to-text",
        description="Useful when you need to read text content (file or URL)",
        args_schema=TextToTextInput,
        return_direct=False,
    )
