from dataclasses import dataclass
from typing import List


@dataclass
class Chat_Settings:
    """
    Store all application persistent keys.
    """

    geometry: str = "708x437+0+0"
    theme: str = "dark"
    always_on_top: bool = False
    last_conv_id: int = None
    last_assistant: int = None
    last_api_type: str = None

    def keys(self) -> List:
        """Return all settings keys."""
        return [k for k in dir(self) if not k.startswith("_")]


SETTINGS = Chat_Settings()
