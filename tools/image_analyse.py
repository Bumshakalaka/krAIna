from pathlib import Path
from typing import Dict

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool

from libs.utils import convert_user_query

load_dotenv(find_dotenv())


class ImageAnalyseInput(BaseModel):
    uri: str = Field(description="Image to analyse. It can be url or local file")
    prompt: str = Field(description="What to do, how to analyse the image")


def image_analyse(uri: str, prompt: str, system_prompt: str = "", model: str = "A", force_api: str = None):
    """
    Analyze an image using an assistant.

    If the URI is not a valid HTTP link, it checks if the file exists locally.
    Constructs a prompt and runs it through the assistant.

    :param uri: The URI of the image can be an HTTP link or a local file path.
    :param prompt: A textual prompt providing context or instructions for analysis.
    :param system_prompt: A textual system prompt providing global instruction for analysis.
    :param model: The name of the model to be used for embedding.
    :param force_api: The API type: openai, azure, anthropic.
    :return: The content result from the assistant's analysis.
    """
    if not uri.startswith("http"):
        if not Path(uri).exists():
            return f"'{uri}' file not exists"
        uri = f"file://{Path(uri).resolve()}"
    from assistants.base import Assistant  # noqa

    llm = Assistant()
    llm.force_api = force_api
    llm.prompt = system_prompt
    llm.model = model
    llm.temperature = 1.0
    user_prompt = f"{prompt}\n![screen]({uri})\nUse fewest words possible and look closely."
    ret = llm.run(convert_user_query(user_prompt), use_db=False)
    return ret.content


def init_image_analysis(tool_setting: Dict) -> BaseTool:
    """
    Initialize the image analysis tool with the given settings.

    Sets up a structured tool for image analysis by partially applying
    the image_analyse function with a provided assistant.

    :param tool_setting: A dictionary containing tool settings, including an assistant.
    :return: A configured StructuredTool instance for image analysis.
    """
    return StructuredTool.from_function(
        func=(
            lambda model, force_api, system_prompt: lambda uri, prompt: image_analyse(
                uri, prompt, system_prompt, model, force_api
            )
        )(
            model=tool_setting.get("model", "A"),
            force_api=tool_setting["assistant"].force_api,
            system_prompt="",
        ),
        name="image-analysis",
        description="Useful when you need to analyse the image or screenshot",
        args_schema=ImageAnalyseInput,
        return_direct=True,
    )
