"""Left Sidebar window."""
import functools
import logging
from pathlib import Path
from tkinter import ttk
import tkinter as tk
from typing import List, Tuple

from chat.base import ai_assistants, APP_EVENTS

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
        ttk.Button(self, text="NEW CHAT", command=self.new_chat).pack(side=tk.TOP, fill=tk.X)
        self.chats = ttk.LabelFrame(self, text="Saved chats")
        self.chats.pack(side=tk.TOP, fill=tk.X)

        fr = ttk.LabelFrame(self, text="Assistants", labelanchor="n")
        for assistant in ai_assistants.keys():
            ttk.Radiobutton(
                fr,
                text=assistant,
                variable=self.root.selected_assistant,
                value=assistant,
            ).pack(side=tk.TOP, fill=tk.X)
        ttk.Button(fr, text="RELOAD").pack(side=tk.BOTTOM, fill=tk.X)
        fr.pack(side=tk.BOTTOM, fill=tk.X)

    def list_saved_chats(self, conversations: List[Tuple[int, str, str, bool]]):
        """
        Callback on UPDATE_SAVED_CHATS event.

        Create chat history entries.

        :param conversations: list of the active conversations
        :return:
        """
        for n in list(self.chats.children.keys()):
            self.chats.children[n].destroy()
        for conversation in conversations:
            ttk.Button(
                self.chats,
                text=conversation[0],
                command=functools.partial(self.get_chat, conversation[0]),
            ).pack(side=tk.TOP, fill=tk.X)

    def new_chat(self):
        """New chat."""
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)

    def get_chat(self, conv_id: int):
        """
        Callback on chat entry to get and load conversion_id chat

        :param conv_id: conversion_id
        :return:
        """
        self.root.post_event(APP_EVENTS.GET_CHAT, conv_id)
