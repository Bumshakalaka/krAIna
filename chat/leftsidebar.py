"""Left Sidebar window."""
import functools
import logging
from pathlib import Path
from tkinter import ttk
import tkinter as tk
from typing import List
from tktooltip import ToolTip

from assistants.assistant import AssistantType, AssistantResp
from chat.base import APP_EVENTS
import chat.chat_persistence as chat_persistence
from libs.db.model import Conversations

logger = logging.getLogger(__name__)


class LeftSidebar(ttk.Frame):
    """Create left sidebar."""

    def __init__(self, parent):
        """
        Initialize the left sidebar.

        :param parent: Main App
        """
        super().__init__(parent)
        self._chat_history_dir = Path(__file__).parent / "../chat_history"
        self.root = parent
        self.root.bind_on_event(APP_EVENTS.UPDATE_SAVED_CHATS, self.list_saved_chats)
        self.root.bind_on_event(APP_EVENTS.UPDATE_AI, self.list_assistsnts)
        but = ttk.Button(self, text="NEW CHAT", command=self.new_chat)
        ToolTip(but, msg="Create new chat", follow=False, delay=0.5)
        but.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        self.chats = ttk.LabelFrame(self, text="Last chats")
        self.chats.pack(side=tk.TOP, fill=tk.X)

        self.assistants = ttk.LabelFrame(self, text="Assistants", labelanchor="n")
        self.list_assistsnts()
        self.assistants.pack(side=tk.BOTTOM, fill=tk.X)
        but = ttk.Button(self, text="RELOAD", command=self.reload_ai)
        ToolTip(but, msg="Reload Assistants and Snippets", follow=False, delay=0.5)
        but.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)

    def list_assistsnts(self, *args):
        for n in list(self.assistants.children.keys()):
            self.assistants.children[n].destroy()
        for name, assistant in self.root.ai_assistants.items():
            name_ = name if assistant.type == AssistantType.SIMPLE else f"{name}(tools)"
            rbut = ttk.Radiobutton(
                self.assistants,
                text=name_,
                variable=self.root.selected_assistant,
                value=name,
                command=self.assistant_change,
            )
            msg_ = assistant.description if assistant.description else name_
            if assistant.type == AssistantType.WITH_TOOLS:
                tools_ = "\n- " + "\n- ".join(assistant.tools)
                msg_ += f"\nTools:{tools_}"
            ToolTip(rbut, msg=msg_, follow=False, delay=0.5)
            rbut.pack(side=tk.TOP, fill=tk.X)

    def assistant_change(self, *args):
        chat_persistence.SETTINGS.last_assistant = self.root.selected_assistant.get()
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                self.root.conv_id,
                "not used",
                self.root.ai_assistants[self.root.selected_assistant.get()].tokens_used(self.root.conv_id),
            ),
        )
        self.root.post_event(APP_EVENTS.UPDATE_STATUS_BAR_API_TYPE, chat_persistence.SETTINGS.last_api_type)

    def list_saved_chats(self, conversations: List[Conversations]):
        """
        Callback on UPDATE_SAVED_CHATS event.

        Create chat history entries.

        :param conversations: list of the active conversations
        :return:
        """
        for n in list(self.chats.children.keys()):
            self.chats.children[n].destroy()
        for conversation in conversations:
            name = conversation.name if conversation.name else f"ID:{conversation.conversation_id}"
            but = ttk.Button(
                self.chats,
                text=name,
                command=functools.partial(self.get_chat, conversation.conversation_id),
            )
            if conversation.description:
                ToolTip(but, msg=conversation.description, delay=0.5, follow=False)
            but.bind("<ButtonRelease-3>", functools.partial(self.deactivate_chat, conversation.conversation_id))
            but.pack(side=tk.TOP, fill=tk.X, pady=2, padx=4)

    def deactivate_chat(self, conv_id: int, event: tk.Event):
        """Deactivate chat."""
        self.root.post_event(APP_EVENTS.DEL_CHAT, int(conv_id))

    def new_chat(self):
        """New chat."""
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                None,
                "not used",
                self.root.ai_assistants[self.root.selected_assistant.get()].tokens_used(None),
            ),
        )

    def reload_ai(self):
        """Reload assistants and snippets"""
        self.root.post_event(APP_EVENTS.RELOAD_AI, None)

    def get_chat(self, conv_id: int):
        """
        Callback on chat entry to get and load conversion_id chat

        :param conv_id: conversion_id
        :return:
        """
        self.root.post_event(APP_EVENTS.GET_CHAT, conv_id)
