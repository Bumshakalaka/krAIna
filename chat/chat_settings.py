from dataclasses import dataclass
from typing import List


@dataclass
class chat_settings:
    """
    Store all chat application settings keys.
    """

    default_assistant: str = None
    theme: str = "dark"
    always_on_top: bool = False
    visible_last_chats: int = 10

    def keys(self) -> List:
        """Return all settings keys."""
        return [k for k in dir(self) if not (k.startswith("_") or callable(k) or k == "keys")]


SETTINGS = chat_settings()
