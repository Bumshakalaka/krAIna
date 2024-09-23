import logging
import os
from pathlib import Path
from typing import List

import yaml
from langchain_core.tools import BaseTool

from libs.utils import import_module, find_lands

logger = logging.getLogger(__name__)

_AVAILABLE_TOOLS = {}

_tools_sets = find_lands("tools", Path(__file__).parent)
for _p in _tools_sets:
    if (_p / "include.py").exists():
        _AVAILABLE_TOOLS.update(getattr(import_module(_p / "include.py"), "SUPPORTED_TOOLS"))


def get_and_init_tools(tools: List[str], assistant=None) -> List[BaseTool]:
    """
    Init and get tools for assistant.

    Validation of tools required by assistant is done on config.yaml load.

    :param tools: List of tools specified in the assistant config.yaml
    :param assistant: Assistant object [BaseAssistant] which will call the tools
    :return: list of tool objects
    """
    # TODO: What will happen when snippets instead of assistants will use tools
    if (Path(__file__).parent / "../config.yaml").resolve().exists():
        with open((Path(__file__).parent / "../config.yaml").resolve(), "r") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
    else:
        logger.warning(
            f"{(Path(__file__).parent / '../config.yaml').resolve()} does not exist. No tools settings available"
        )
        data = {}
    tools_settings = data.get("tools", {})
    init_tools = []
    for tool_name, init_cmd in _AVAILABLE_TOOLS.items():
        if tool_name.lower() in tools:
            ret = init_cmd(
                dict(
                    tools_settings.get(tool_name, {}),
                    config_dir=str((Path(__file__).parent / "../config.yaml").resolve().parent),
                    assistant=assistant,
                )
            )
            if isinstance(ret, list):
                [init_tools.append(r) for r in ret]
            else:
                init_tools.append(ret)
    return init_tools


def get_available_tools() -> List[str]:
    """Return all available and supported tools to use."""
    return list([x for x in _AVAILABLE_TOOLS.keys() if not x.startswith("_")])
