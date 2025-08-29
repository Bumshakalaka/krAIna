"""Text to image generation tool.

This module provides functionality to generate images from text descriptions
using AI models like DALL-E. It supports various image sizes and formats.
"""

from typing import Dict, Literal

from aenum import Enum
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

import kraina.libs.images as images
from kraina.libs.llm import llm_client, map_model


class ImageSize(Enum):  # type: ignore
    """Enumeration of available image sizes for generation.

    Defines the supported image sizes and their descriptions.
    """

    _init_ = "value __doc__"
    SMALL_SQUARE = "SMALL_SQUARE", "256x256 resolution"
    MEDIUM_SQUARE = "MEDIUM_SQUARE", "512x512 resolution"
    LARGE_SQUARE = "LARGE_SQUARE", "1024x1024 resolution"
    LARGE_LANDSCAPE = "LARGE_LANDSCAPE", "1792x1024 resolution"
    LARGE_PORTRAIT = "LARGE_PORTRAIT", "1024x1792 resolution"


GENERATOR_PROPS = {
    "DALLE2": {
        "SIZE": {
            "SMALL_SQUARE": "256x256",
            "MEDIUM_SQUARE": "512x512",
            "LARGE_SQUARE": "1024x1024",
            "LARGE_LANDSCAPE": "1024x1024",
            "LARGE_PORTRAIT": "1024x1024",
        },
        "MULTIPLE_IMAGES": True,
    },
    "DALLE3": {
        "SIZE": {
            "SMALL_SQUARE": "1024x1024",
            "MEDIUM_SQUARE": "1024x1024",
            "LARGE_SQUARE": "1024x1024",
            "LARGE_LANDSCAPE": "1792x1024",
            "LARGE_PORTRAIT": "1024x1792",
        },
        "MULTIPLE_IMAGES": False,
    },
}


class TextToImageInput(BaseModel):
    """Input schema for text to image generation.

    Defines the required input parameters for generating images from text.
    """

    query: str = Field(description="Image description")
    size: ImageSize = Field(
        ImageSize.SMALL_SQUARE, description="Size of the image to generate, default is SMALL_SQUARE"
    )  # type: ignore
    no_of_images: int = Field(1, description="How many image to generate")


def text_to_image(
    query: str,
    size: (
        ImageSize | Literal["SMALL_SQUARE", "MEDIUM_SQUARE", "LARGE_SQUARE", "LARGE_LANDSCAPE", "LARGE_PORTRAIT"]  # type: ignore  # noqa: F821
    ) = ImageSize.SMALL_SQUARE,  # type: ignore
    no_of_images: int = 1,
    model: str = "dall-e-3",
    force_api: str | None = None,
):
    """Generate images from a text query using a specified model and size.

    This function interfaces with an LLM client to generate images from a text prompt.
    It supports different image sizes and models, and can generate multiple images.

    :param query: The text prompt to generate images from.
    :param size: The desired size of the image(s), default is ImageSize.SMALL_SQUARE.
    :param no_of_images: The number of images to generate, default is 1.
    :param model: The model to use for image generation, default is "dall-e-3".
    :param force_api: Optional parameter to force a specific API type (openai, azure).
    :return: A string containing markdown formatted images with descriptions.
    """
    client = llm_client(force_api_type=force_api)

    generator = "DALLE2" if "2" in model else "DALLE3"
    response = client.images.generate(  # type: ignore
        model=map_model(model, force_api),
        prompt=query,
        n=1 if GENERATOR_PROPS[generator]["MULTIPLE_IMAGES"] else no_of_images,
        size=GENERATOR_PROPS[generator]["SIZE"][size.name if isinstance(size, ImageSize) else size],
        response_format="url",
    )

    # download and convert images into data uri
    # they can be stored in database but - big image == 5MB or more of data
    ret = []
    if response.data:
        for i in range(min(no_of_images, len(response.data))):
            data_item = response.data[i]
            if data_item and data_item.url:
                img = images.chat_images.create_from_url(data_item.url, "", False)
                revised_prompt = getattr(data_item, "revised_prompt", query)
                ret.append(f"![{img}]({images.chat_images.get_file_url(img)})\n\nPrompt: `{revised_prompt}`")
    return "\n\n".join(ret)


def init_text_to_image(tool_setting: Dict) -> BaseTool:
    """Initialize the text-to-image tool with the given settings.

    This function creates a StructuredTool instance for generating images
    from text descriptions using the specified tool settings.

    :param tool_setting: Dictionary containing settings for the tool,
                         including the 'assistant' key with 'force_api'.
    :return: An instance of BaseTool configured for text-to-image generation.
    """
    return StructuredTool.from_function(
        func=(
            lambda model, force_api: lambda query, size, no_of_images=1: text_to_image(
                query, size, no_of_images, model, force_api
            )
        )(
            model=tool_setting.get("model", "dall-e-3"),
            force_api=tool_setting["assistant"].force_api,
        ),
        name="text-to-image",
        description="A wrapper around text-to-image API. "
        "Useful for when you need to generate images from a text description.",
        args_schema=TextToImageInput,
        return_direct=False,
    )
