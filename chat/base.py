"""Base functions."""
import enum
from typing import List

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
    GET_CHAT = "<<GetChat>>"
    LOAD_CHAT = "<<LoadChat>>"
    DEL_CHAT = "<<DeactivateChat>>"
    DESCRIBE_NEW_CHAT = "<<DescribeNewChat>>"
    UPDATE_SAVED_CHATS = "<<UpdateSavedChats>>"
    ADD_NEW_CHAT_ENTRY = "<<NewChatEntry>>"
    UNBLOCK_USER = "<<UnblockUser>>"
    SHOW_APP = "<<ShowApp>>"
    HIDE_APP = "<<MinimizeApp>>"


def api_public() -> List:
    return [APP_EVENTS.SHOW_APP.name, APP_EVENTS.HIDE_APP.name]


ai_assistants = Assistants()
ai_snippets = Snippets()
