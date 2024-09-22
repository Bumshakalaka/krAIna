import json
from typing import Dict

from aenum import Enum
import os
import tempfile
from io import BytesIO

import requests
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool
import chat.chat_images as chat_images

load_dotenv(find_dotenv())


class ImageSize(Enum):
    _init_ = "value __doc__"
    LOW = "256x256", "Low resolution 256x256"
    MEDIUM = "512x512", "Medium resolution 512x512"
    HIGH = "1024x1024", "High resolution 1024x1024"


class TextToImageInput(BaseModel):
    query: str = Field(description="Image description")
    size: ImageSize = Field(ImageSize.LOW, description="Size of the image to generate")
    no_of_images: int = Field(1, description="How many image to generate")


def text_to_image(query: str, size: ImageSize, no_of_images: int = 1):
    """A wrapper around text-to-image API. Useful for when you need to generate images from a text description."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    # call the OpenAI API
    response = client.images.generate(
        model="dall-e-2",
        prompt=query,
        n=no_of_images,
        size=size.value,
        response_format="url",
    )
    # ret = []
    # for i in range(no_of_images):
    #     with BytesIO() as fd:
    #         fd.write(requests.get(response.data[i].url).content)
    #         fd.seek(0)
    #         img = chat_images.chat_images.create_from_file(fd)
    #     ret.append(f"![{img}]({chat_images.chat_images.get_url(img)})")
    ret_content = {"images": []}
    for i in range(no_of_images):
        ret_content["images"].append(dict(url=response.data[i].url, revised_prompt=response.data[i].revised_prompt))
    return json.dumps(ret_content)


def init_text_to_image(tool_setting: Dict) -> BaseTool:
    return StructuredTool.from_function(
        func=text_to_image,
        name="Text-to-Image",
        description="A wrapper around text-to-image API. Useful for when you need to generate images from a text description.",
        args_schema=TextToImageInput,
        return_direct=False,
    )
