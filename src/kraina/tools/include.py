"""Expose the tools to krAIna.

To make a tool available to others in krAIna, you need to follow these steps:

1. Find or develop a tool derived from BaseTool.
    1.1. Check https://python.langchain.com/v0.2/docs/integrations/tools/ for build-in in langchain tools
    1.2. Check https://python.langchain.com/v0.2/docs/integrations/toolkits/ for build-in in langchain tools
    1.3. Check https://python.langchain.com/v0.2/docs/how_to/custom_tools/ how to create your own tool
2. Create an initialization function that:
    2.1. Must accept one parameter, tool_settings (even if you don't have any settings).
    2.2. Must return BaseTool or List[BaseTool].
3. Add your tool to the SUPPORTED_TOOLS dictionary. The name of your tool is the key of the SUPPORTED_TOOLS dictionary.

The initialization of the tool (calling the init function) occurs when an Assistant is called,
not when it is initialized.
"""

import os
from pathlib import Path
from typing import Dict, List

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools import BraveSearch, WolframAlphaQueryRun
from langchain_community.utilities import WolframAlphaAPIWrapper
from langchain_core.tools import BaseTool

from kraina.tools.audio_to_text import init_audio_to_text
from kraina.tools.image_analyse import init_image_analysis
from kraina.tools.joplin import init_joplin_search
from kraina.tools.text_to_image import init_text_to_image
from kraina.tools.text_to_text import init_text_to_text
from kraina.tools.vector_store import init_vector_search


class MyWolframAlphaQueryRun(WolframAlphaQueryRun):
    """A class to run WolframAlpha queries using an API wrapper."""

    @classmethod
    def from_api_wrapper(cls, api_wrapper):
        """Create an instance of MyWolframAlphaQueryRun from an API wrapper.

        :param api_wrapper: An instance of the API wrapper to interface with WolframAlpha.
        :return: An instance of MyWolframAlphaQueryRun.
        """
        return cls(api_wrapper=api_wrapper)


def init_wolfram_alpha(*args) -> BaseTool:  # noqa: ARG001
    """Initialize a WolframAlpha query tool.

    :return: An instance of a WolframAlpha query tool.
    """
    wrapper = WolframAlphaAPIWrapper()
    return MyWolframAlphaQueryRun.from_api_wrapper(wrapper)


def init_web_search(tool_setting: Dict) -> BaseTool:
    """Initialize Brave Web Search tool.

    :param tool_setting: Configuration dict taken from config.yaml file
                         The dict includes only entries from tools.brave_web
    :return:
    """
    return BraveSearch.from_api_key(api_key=os.environ["BRAVE_API_KEY"], search_kwargs={"count": tool_setting["count"]})


def init_file_mgmt(tool_setting: Dict) -> List[BaseTool]:
    """Initialize File Management toolkit.

    :param tool_setting: Configuration dict taken from config.yaml file
                         The dict includes only entries from tools.brave_web
    :return:
    """
    root_dir = Path(os.path.expanduser(tool_setting["working_dir"])).resolve()
    toolkit = FileManagementToolkit(
        root_dir=str(root_dir),
        selected_tools=["file_search", "list_directory"],
    )  # If you don't provide a root_dir, operations will default to the current working directory
    return toolkit.get_tools()


####
SUPPORTED_TOOLS = {
    "brave_web": init_web_search,
    "file_mgmt": init_file_mgmt,
    "wolfram_alpha": init_wolfram_alpha,
    "text-to-image": init_text_to_image,
    "vector-search": init_vector_search,
    "joplin-search": init_joplin_search,
    "audio-to-text": init_audio_to_text,
    "text-to-text": init_text_to_text,
    "image-analysis": init_image_analysis,
}
"""List of supported tools with initialisation function."""
