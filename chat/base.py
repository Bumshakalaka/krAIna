"""Base functions."""
import enum

from assistants.base import Assistants
from snippets.base import Snippets


class APP_EVENTS(enum.Enum):
    """
    App events table.
    """

    QUERY_ASSIST_CREATED = "<<QueryAssistantCreated>>"
    QUERY_TO_ASSISTANT = "<<QueryAssistant>>"
    RESP_FROM_ASSISTANT = "<<AssistantResp>>"
    RESP_FROM_SNIPPET = "<<SkillResp>>"
    QUERY_SNIPPET = "<<QuerySkill>>"
    NEW_CHAT = "<<NewChat>>"
    SAVE_CHAT = "<<SaveChat>>"
    LOAD_CHAT = "<<LoadChat>>"
    UPDATE_SAVED_CHATS = "<<UpdateSavedChats>>"
    UNBLOCK_USER = "<<UnblockUser>>"


ai_assistants = Assistants()
ai_snippets = Snippets()
