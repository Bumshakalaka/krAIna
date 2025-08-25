"""Chat persistence and settings management.

This module provides persistent storage for application settings and
configuration data, including window geometry, theme preferences,
and user interface state.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class chat_persistence:
    """Application settings and persistent data storage.

    Stores all user preferences and application state that should
    persist between sessions, including window positions, theme
    settings, and interface configurations.

    :param geometry: Main window geometry string (width x height + x + y)
    :param theme: Current theme name for the application
    :param always_on_top: Whether the window should stay on top
    :param last_conv_id: Dictionary mapping assistant IDs to last conversation IDs
    :param last_assistant: ID of the last used assistant
    :param last_api_type: Last used API type for AI interactions
    :param last_view_id: ID of the last selected chat view (HTML/text)
    :param show_also_hidden_chats: Whether to display hidden conversations
    :param sashpos_main: Position of the main window sash divider
    :param sashpos_chat: Position of the chat window sash divider
    :param dbg_wnd_geometry: Debug window geometry string
    :param macro_wnd_geometry: Macro window geometry string
    :param copy_to_clipboard: Whether to automatically copy AI responses
    :param database: Database file path for conversation storage
    """

    geometry: str = "708x546+0+0"
    theme: str = "sun-valley-dark"
    always_on_top: bool = False
    last_conv_id: Dict[str, int | None] | None = None
    last_assistant: int | None = None
    last_api_type: str = ""
    last_view_id: int | None = None
    show_also_hidden_chats: bool = False
    sashpos_main: int = 149
    sashpos_chat: int = 288
    dbg_wnd_geometry: str = "708x546+0+0"
    macro_wnd_geometry: str = "708x546+0+0"
    copy_to_clipboard: bool = False
    database: str = "kraina.db"

    def keys(self) -> List:
        """Return all settings keys as a list.

        Provides a list of all configurable settings keys, excluding
        private attributes and methods.

        :return: List of setting key names
        """
        return [k for k in dir(self) if not (k.startswith("_") or callable(k) or k == "keys")]


SETTINGS = chat_persistence()
"""Global settings instance for application-wide access."""


def show_also_hidden_chats():
    """Determine whether hidden chats should be displayed.

    Returns the inverse of the show_also_hidden_chats setting,
    used for filtering conversation lists.

    :return: None if hidden chats should be shown, True if they should be hidden
    """
    return None if SETTINGS.show_also_hidden_chats is True else True
