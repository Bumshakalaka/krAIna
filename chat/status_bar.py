"""Status bar widget."""
import logging
from tkinter import ttk
import tkinter as tk

from tktooltip import ToolTip

from assistants.assistant import AssistantResp
from chat.base import APP_EVENTS
from libs.llm import get_llm_type

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
        self.api_params = tk.StringVar()
        self.label_api_params = ttk.Label(self, relief=tk.SUNKEN, textvariable=self.api_params)
        self.label_api_params.pack(side=tk.LEFT)
        self.label_token_usage.pack(side=tk.LEFT, fill=tk.X)
        self.label_api.pack(side=tk.RIGHT)
        self.root.bind_on_event(APP_EVENTS.UPDATE_STATUS_BAR_API_TYPE, self.update_statusbar_api)
        self.root.bind_on_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS, lambda data: self.after_idle(self.update_statusbar, data)
        )

    def update_statusbar_api(self, data: str):
        """update_statusbar_api"""
        self.api_name.set(get_llm_type(data))
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-bg)")
        self.label_api.configure(background=col)

    def update_statusbar(self, data: AssistantResp):
        """Update status bar."""
        if data.error:
            self.token_usage.set(str(data.error))
            # we have error from LLM call
            self.label_token_usage.configure(background="#ED6A5A")
        else:
            self.api_params.set(str(data.tokens.pop("api")) + " | ")
            self.token_usage.set(str(data.tokens))
            theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
            col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-bg)")
            self.label_token_usage.configure(background=col)
