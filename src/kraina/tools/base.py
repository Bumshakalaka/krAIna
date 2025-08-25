"""Base module for tool initialization and management.

This module provides functionality to dynamically load and initialize tools
that can be used by assistants. It handles tool discovery, configuration,
and instantiation.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from kraina.libs.paths import CONFIG_FILE
from kraina.libs.utils import find_assets, import_module

logger = logging.getLogger(__name__)

_AVAILABLE_TOOLS = {}

_tools_sets = find_assets("tools", Path(__file__).parent)
for _p in _tools_sets:
    if (_p / "include.py").exists():
        _AVAILABLE_TOOLS.update(getattr(import_module(_p / "include.py"), "SUPPORTED_TOOLS"))


def get_and_init_langchain_tools(tools: List[str], assistant=None) -> List[BaseTool]:
    """Initialize and get langchain tools for assistant.

    Validation of tools required by assistant is done on config.yaml load.

    Args:
        tools: List of tools specified in the assistant config.yaml.
        assistant: Assistant object [BaseAssistant] which will call the tools.

    Returns:
        List of tool objects.

    """
    # TODO: What will happen when snippets instead of assistants will use tools
    with open(CONFIG_FILE, "r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
    tools_settings = data.get("tools", {})
    init_tools = []
    for tool_name, init_cmd in _AVAILABLE_TOOLS.items():
        if tool_name.lower() in tools:
            ret = init_cmd(
                dict(
                    tools_settings.get(tool_name, {}),
                    config_dir=str(CONFIG_FILE.parent),
                    assistant=assistant,
                )
            )
            if isinstance(ret, list):
                [init_tools.append(r) for r in ret]
            else:
                init_tools.append(ret)
    return init_tools


def _validate_server_config(server_name: str, server_config: Dict[str, Any]) -> None:
    """Validate MCP server configuration.

    Args:
        server_name: Name of the server being validated.
        server_config: Configuration dictionary for the server.

    Raises:
        ValueError: If server configuration is invalid.

    """
    # Check for URL-based server
    if "url" in server_config:
        url = server_config["url"]
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"Server '{server_name}' has invalid URL: {url}")

        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"Server '{server_name}' URL must start with http:// or https://, got: {url}")

    # Check for stdio-based server
    elif "command" in server_config and "args" in server_config:
        command = server_config["command"]
        args = server_config["args"]

        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"Server '{server_name}' has invalid command: {command}")

        if not isinstance(args, list):
            raise ValueError(f"Server '{server_name}' args must be a list, got {type(args)}")

    else:
        raise ValueError(f"Unknown server configuration format for {server_name}: {server_config}")


def _subs_env_vars(server_config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively substitute environment variables in all string values of server config."""
    mod_env = {}
    for k, v in os.environ.items():
        mod_env["env-" + k] = v

    def substitute(val):
        if isinstance(val, str):
            try:
                return val.format(**mod_env)
            except KeyError as e:
                raise KeyError(f"{val} - env variable {e} not found. Did you add 'env-' in yaml file?")
        if isinstance(val, dict):
            return {k: substitute(v) for k, v in val.items()}
        if isinstance(val, list):
            return [substitute(v) for v in val]
        return val

    return substitute(server_config)  # type: ignore


def _create_mcp_server_config(tools: Optional[List[str]] = None) -> tuple[Dict[str, Dict], dict[str, List[str]]]:
    """Create MCP server config for assistant.

    Args:
        tools: List of tools required by assistant. If None, all MCP tools will be used.

    Returns:
        Dictionary of validated MCP server configurations.
        Dictionary of server names and their included tools.

    """
    tools = tools or []
    # Load tools settings from config.yaml
    with open(CONFIG_FILE, "r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
    tools_settings = data.get("tools", {})
    # Filter tools by type - select only MCP tools
    mcp_servers = {k: v for k, v in tools_settings.items() if v.get("type", "langchain") == "mcp"}
    # Filter tools by name - select only tools that required by assistant
    mcp_servers = {k: v for k, v in mcp_servers.items() if k.lower() in tools} if tools else mcp_servers

    # Convert to MultiServerMCPClient format
    server_configs: dict[str, Dict] = {}
    server_include_tools: dict[str, List[str]] = {}
    for server_name, server_config in mcp_servers.items():
        _validate_server_config(server_name, server_config)

        # Determine transport type based on configuration
        if "url" in server_config:
            url = server_config["url"]
            # Select transport based on URL ending
            # /mcp -> streamable_http (modern), /sse -> sse (legacy, deprecated)
            transport = "sse" if url.rstrip("/").endswith("/sse") else "streamable_http"

            if (headers := server_config.get("headers", {})) and headers.get("Authorization"):
                # if in header we have Authorization key
                auth = headers["Authorization"].split(" ")
                # if in Authorization key there is no Bearer word at the beginning, add it
                if len(auth) == 1:
                    headers["Authorization"] = "Bearer " + auth[0]
                else:
                    headers["Authorization"] = " ".join(auth)
            server_configs[server_name] = {
                "url": url,
                "transport": transport,
                "headers": headers,
            }
            logger.debug(f"Configured {transport} transport for {server_name}: {url}")

        else:
            # stdio transport
            server_configs[server_name] = {
                "command": server_config["command"],
                "args": server_config["args"],
                "transport": "stdio",
                "env": server_config.get("env", {}),
            }
            logger.debug(
                f"Configured stdio transport for {server_name}: {server_config['command']} "
                f"{' '.join(server_config['args'])}"
            )
        server_include_tools[server_name] = server_config.get("include_tools", [])

    logger.debug(f"Loaded {len(server_configs)} MCP server configurations")
    return _subs_env_vars(server_configs), server_include_tools


async def get_and_init_mcp_tools(tools: List[str]) -> List[BaseTool]:
    """Initialize and get MCP tools for assistant.

    Args:
        tools: List of MCP tools specified in the assistant config.yaml.

    Returns:
        List of MCP tool objects.

    """
    server_configs, server_include_tools = _create_mcp_server_config(tools)
    logger.info(f"Initializing MultiServerMCPClient with {len(server_configs)} servers")
    matching_tools = []
    for server, server_config in server_configs.items():
        client = MultiServerMCPClient(connections={server: server_config})  # type: ignore
        try:
            toolkit = await client.get_tools()
        except Exception:
            logger.error(f"{server} error. Check server_config in config.yaml and reload assistant")
            continue
        if server_include_tools.get(server, []):
            for tool in toolkit:
                if any(pattern.lower() in tool.name.lower() for pattern in server_include_tools[server]):
                    matching_tools.append(tool)
        else:
            matching_tools.extend(toolkit)

    logger.info(f"Found {len(matching_tools)} tools matching patterns")
    return matching_tools


def get_available_langchain_tools() -> List[str]:
    """Return all available and supported langchain tools to use.

    Returns:
        List of available tool names.

    """
    return list([x for x in _AVAILABLE_TOOLS.keys() if not x.startswith("_")])


def get_available_mcp_tools() -> List[str]:
    """Return all available and supported MCP tools to use.

    Returns:
        List of available tool names.

    """
    try:
        return list(_create_mcp_server_config()[0].keys())
    except Exception as e:
        logger.error(f"Error getting available MCP tools: {e}")
        return []


def get_available_tools() -> List[str]:
    """Return all available and supported tools to use.

    Returns:
        List of available tool names.

    """
    return get_available_langchain_tools() + get_available_mcp_tools()


def get_assistant_tools(assistant: str) -> List[str]:
    """Return all tools for assistant.

    Returns:
        List of available tool names.

    """
    with open(CONFIG_FILE, "r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
    return data.get("assistants", {}).get(assistant, {}).get("tools", [])
