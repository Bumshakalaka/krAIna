"""Status bar widget."""
import logging
from tkinter import ttk
import tkinter as tk

from tktooltip import ToolTip

logger = logging.getLogger(__name__)


class StatusBar(tk.Frame):
    """Status Bar."""

    def __init__(self, parent):
        """
        Initialize status bar.

        :param parent: main App
        """
        super().__init__(parent, padx=2, pady=2)
        self.root = parent
        ttk.Separator(self).pack(side=tk.TOP, fill=tk.X)
        self.token_usage = tk.StringVar()
        self.label_token_usage = ttk.Label(self, relief=tk.SUNKEN, textvariable=self.token_usage)
        ToolTip(self.label_token_usage, msg=self.token_usage.get, follow=False, delay=0.5)
        self.model_name = tk.StringVar()
        self.label_model = ttk.Label(self, relief=tk.SUNKEN, textvariable=self.model_name, width=20)
        self.label_model.pack(side=tk.LEFT, fill=tk.X)
        self.label_token_usage.pack(side=tk.LEFT)

    def update_statusbar(self, data):
        """Update status bar."""
        self.token_usage.set(data.get("token_usage", ""))
        self.model_name.set(data.get("model_name", ""))
        if data.get("model_name") is None:
            # we have error from LLM call
            self.label_token_usage.configure(background="#ED6A5A")
        else:
            theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
            col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-bg)")
            self.label_token_usage.configure(background=col)
