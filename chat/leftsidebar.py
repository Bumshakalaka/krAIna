"""Left Sidebar window."""
import logging
from tkinter import ttk
import tkinter as tk

from base import ai_assistants, APP_EVENTS

logger = logging.getLogger(__name__)


class LeftSidebar(ttk.Frame):
    """Create left sidebar."""

    def __init__(self, parent):
        """
        Initialize the left sidebar.

        :param parent: Main App
        """
        super().__init__(parent)
        self.root = parent
        ttk.Button(self, text="NEW CHAT", command=self.new_chat).pack(
            side=tk.TOP, fill=tk.X
        )

        fr = ttk.LabelFrame(self, text="Assistants", labelanchor="n")
        for assistant in ai_assistants.keys():
            ttk.Radiobutton(
                fr,
                text=assistant,
                variable=self.master.selected_assistant,
                value=assistant,
            ).pack(side=tk.TOP, fill=tk.X)
        ttk.Button(fr, text="RELOAD").pack(side=tk.BOTTOM, fill=tk.X)
        fr.pack(side=tk.BOTTOM, fill=tk.X)

    def new_chat(self):
        """New chat."""
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)
