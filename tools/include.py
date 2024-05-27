import os
from typing import Dict

from langchain_community.tools import BraveSearch
from langchain_core.tools import BaseTool


def init_web_search(tool_setting: Dict) -> BaseTool:
    return BraveSearch.from_api_key(api_key=os.environ["BRAVE_API_KEY"], search_kwargs={"count": 3})


####
SUPPORTED_TOOLS = {"brave_web": init_web_search}
