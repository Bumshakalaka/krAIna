"""Chat application settings and configuration.

This module provides configuration management for the chat application,
including default assistant selection, theme preferences, and display
options.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class chat_settings:
    """Chat application configuration settings.

    Stores user preferences and configuration options for the chat
    application interface and behavior.

    :param default_assistant: Name of the default AI assistant to use
    :param theme: Application theme preference (dark/light)
    :param always_on_top: Whether the application window should stay on top
    :param visible_last_chats: Number of recent chats to display in the list
    :param editor: Path to the preferred text editor for external editing
    """

    default_assistant: str | None = None
    theme: str = "dark"
    always_on_top: bool = False
    visible_last_chats: int = 10
    editor: str | None = None

    def keys(self) -> List:
        """Return all settings keys as a list.

        Provides a list of all configurable settings keys, excluding
        private attributes and methods.

        :return: List of setting key names
        """
        return [k for k in dir(self) if not (k.startswith("_") or callable(k) or k == "keys")]


SETTINGS = chat_settings()
"""Global chat settings instance for application-wide access."""
