import functools
from typing import Dict

from aenum import Enum

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool

import chat.chat_images as chat_images
from libs.llm import image_client, map_model

load_dotenv(find_dotenv())


class ImageSize(Enum):
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
    query: str = Field(description="Image description")
    size: ImageSize = Field(
        ImageSize.SMALL_SQUARE, description="Size of the image to generate, default is SMALL_SQUARE"
    )
    no_of_images: int = Field(1, description="How many image to generate")


def text_to_image(model: str, force_api: str, query: str, size: ImageSize, no_of_images: int = 1):
    """A wrapper around text-to-image API. Useful for when you need to generate images from a text description."""
    client = image_client(force_api_type=force_api)

    generator = "DALLE2" if "2" in model else "DALLE3"
    response = client.images.generate(
        model=model,
        prompt=query,
        n=1 if GENERATOR_PROPS[generator]["MULTIPLE_IMAGES"] else no_of_images,
        size=GENERATOR_PROPS[generator]["SIZE"][size.name],
        response_format="url",
    )

    # download and convert images into data uri
    # they can be stored in database but - big image == 5MB or more of data
    ret = []
    for i in range(no_of_images):
        img = chat_images.chat_images.create_from_url(response.data[i].url, None, False)
        ret.append(f"![{img}]({chat_images.chat_images.get_url(img)})\n\nPrompt: `{response.data[i].revised_prompt}`")
    return "\n\n".join(ret)


def init_text_to_image(tool_setting: Dict) -> BaseTool:
    """
    Initialize the text-to-image tool with the given settings.

    This function creates a StructuredTool instance for generating images
    from text descriptions using the specified tool settings.

    :param tool_setting: Dictionary containing settings for the tool,
                         including the 'assistant' key with 'force_api'.
    :return: An instance of BaseTool configured for text-to-image generation.
    """
    return StructuredTool.from_function(
        func=functools.partial(
            text_to_image,
            map_model(tool_setting.get("model", "dall-e-3"), tool_setting["assistant"].force_api),
            tool_setting["assistant"].force_api,
        ),
        name="text-to-image",
        description="A wrapper around text-to-image API. Useful for when you need to generate images from a text description.",
        args_schema=TextToImageInput,
        return_direct=True,
    )
