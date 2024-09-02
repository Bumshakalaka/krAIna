import functools
import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from chat.macro_window import MacroWindow

logger = logging.getLogger(__name__)


class MacrosMenu(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for Macros."""
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        for name, macro in self.parent.ai_macros.items():
            self.add_command(label=name, command=functools.partial(MacroWindow, self.parent, macro))
