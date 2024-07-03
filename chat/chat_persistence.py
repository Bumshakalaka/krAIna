from dataclasses import dataclass
from typing import List


@dataclass
class chat_persistence:
    """
    Store all application persistent keys.
    """

    geometry: str = "708x546+0+0"
    theme: str = "dark"
    always_on_top: bool = False
    last_conv_id: int = None
    last_assistant: int = None
    last_api_type: str = ""
    last_view_id: int = None
    show_also_hidden_chats: bool = False
    sashpos_main: int = 149
    sashpos_chat: int = 288

    def keys(self) -> List:
        """Return all settings keys."""
        return [k for k in dir(self) if not (k.startswith("_") or callable(k) or k == "keys")]


SETTINGS = chat_persistence()
show_also_hidden_chats = lambda: None if SETTINGS.show_also_hidden_chats is True else True
