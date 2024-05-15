"""Left Sidebar window."""
import functools
import logging
from pathlib import Path
from tkinter import ttk
from tkinter import filedialog, simpledialog
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
        self._chat_history_dir = Path(__file__).parent / "../chat_history"
        self.root = parent
        self.root.bind_on_event(APP_EVENTS.UPDATE_SAVED_CHATS, self.update_saved_chats)
        ttk.Button(self, text="NEW CHAT", command=self.new_chat).pack(
            side=tk.TOP, fill=tk.X
        )
        ttk.Button(self, text="SAVE CHAT", command=self.save_chat).pack(
            side=tk.TOP, fill=tk.X
        )
        ttk.Button(self, text="LOAD CHAT", command=self.load_chat).pack(
            side=tk.TOP, fill=tk.X
        )
        self.chats = ttk.LabelFrame(self, text="Saved chats")
        self.chats.pack(side=tk.TOP, fill=tk.X)
        self.update_saved_chats()

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

    def update_saved_chats(self, *args):
        for n in list(self.chats.children.keys()):
            self.chats.children[n].destroy()
        for chat in self._chat_history_dir.glob("*.yaml"):
            ttk.Button(
                self.chats,
                text=chat.stem,
                command=functools.partial(self.load_chat, chat),
            ).pack(side=tk.TOP, fill=tk.X)

    def new_chat(self):
        """New chat."""
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)

    def save_chat(self):
        """Trigger to save current chat."""
        self._chat_history_dir.mkdir(exist_ok=True)
        filetypes = (("yaml files", "*.yaml"),)
        file_to_save = filedialog.asksaveasfilename(
            title="Save chat", initialdir=self._chat_history_dir, filetypes=filetypes
        )
        if file_to_save:
            description = simpledialog.askstring(
                "Chat description",
                "Describe chat",
                initialvalue=Path(file_to_save).name,
            )
            self.root.post_event(
                APP_EVENTS.SAVE_CHAT,
                dict(file_path=file_to_save, description=description),
            )

    def load_chat(self, file_to_load=None):
        """
        Load chat from file.

        :param file_to_load: If passed, load this chat from file. If not, create File selection Dialog
        :return:
        """
        if not file_to_load:
            file_to_load = filedialog.askopenfilename(
                title="Load chat", initialdir=Path(__file__).parent
            )
        self.root.post_event(
            APP_EVENTS.LOAD_CHAT, file_to_load
        ) if file_to_load else None
