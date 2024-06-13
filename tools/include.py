"""
Expose the tools to krAIna.

To make a tool available to others in krAIna, you need to follow these steps:

1. Find or develop a tool that is derived from BaseTool.
2. Create an initialization function that:
    2.1. Must accept one parameter, tool_settings (even if you don't have any settings).
    2.2. Must return BaseTool or List[BaseTool].
3. Add your tool to the SUPPORTED_TOOLS dictionary. The name of your tool is the key of the SUPPORTED_TOOLS dictionary.

The initialization of the tool (calling the init function) occurs when an Assistant is called,
not when it is initialized.
"""
import os
from typing import Dict

from langchain_community.tools import BraveSearch
from langchain_core.tools import BaseTool


def init_web_search(tool_setting: Dict) -> BaseTool:
    """
    Initialize Brave Web Search tool.

    :param tool_setting: Configuration dict taken from config.yaml file
                         The dict includes only entries from tools.brave_web
    :return:
    """
    return BraveSearch.from_api_key(api_key=os.environ["BRAVE_API_KEY"], search_kwargs={"count": tool_setting["count"]})


####
SUPPORTED_TOOLS = {"brave_web": init_web_search}
"""List of supported tools with initialisation function."""
