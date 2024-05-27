"""Base functions."""
import enum
from typing import Dict


class APP_EVENTS(enum.Enum):
    """
    App events table.
    """

    QUERY_ASSIST_CREATED = "<<QueryAssistantCreated>>"
    QUERY_TO_ASSISTANT = "<<QueryAssistant>>"
    RESP_FROM_ASSISTANT = "<<AssistantResp>>"
    RESP_FROM_SNIPPET = "<<SkillResp>>"
    RESP_FROM_TOOL = "<<ToolResp>>"
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
    RELOAD_AI = "<<ReloadAIStuff>>"
    UPDATE_AI = "<<UpdateAIStuff>>"
    UPDATE_THEME = "<<UpdateTheme>>"


def app_interface() -> Dict:
    """
    Return App interface.

    :return: Dict(command, description)
    """
    return {
        APP_EVENTS.SHOW_APP.name: "Trigger to display the application",
        APP_EVENTS.HIDE_APP.name: "Trigger to minimize the application",
    }
