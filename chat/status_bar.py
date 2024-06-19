"""Status bar widget."""
import logging
from tkinter import ttk
import tkinter as tk

from tktooltip import ToolTip

from chat.base import APP_EVENTS
from libs.llm import isAzureAI

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
        ToolTip(self.label_token_usage, msg=self.token_usage.get, follow=False, delay=0.5, y_offset=-50)
        self.api_name = tk.StringVar()
        self.label_api = ttk.Label(self, relief=tk.SUNKEN, textvariable=self.api_name, width=10, justify=tk.RIGHT)
        self.model_name = tk.StringVar()
        self.label_model = ttk.Label(self, relief=tk.SUNKEN, textvariable=self.model_name, width=20)
        self.label_model.pack(side=tk.LEFT, fill=tk.X)
        self.label_token_usage.pack(side=tk.LEFT)
        self.label_api.pack(side=tk.RIGHT)
        self.root.bind_on_event(APP_EVENTS.UPDATE_STATUS_BAR, self.update_statusbar_api)

    def update_statusbar_api(self, data: str):
        """update_statusbar_api"""
        self.api_name.set("Azure" if isAzureAI(data) else "OpenAi")
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-bg)")
        self.label_api.configure(background=col)

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
