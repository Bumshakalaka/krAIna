"""Status bar widget."""
import logging
from tkinter import ttk
import tkinter as tk

from tktooltip import ToolTip

import chat.chat_persistence as chat_persistence
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
        self.api_name_descr = tk.StringVar(
            self,
            f"Selected LLM to use based on:\n"
            f"1. Chat settings: '{chat_persistence.SETTINGS.last_api_type}'\n"
            f"2. Assistant force_api setting: '{self.root.ai_assistants[self.root.selected_assistant.get()].force_api}'",
        )
        self.label_api = ttk.Label(self, relief=tk.SUNKEN, textvariable=self.api_name, width=10, justify=tk.RIGHT)
        ToolTip(
            self.label_api,
            msg=self.api_name_descr.get,
            follow=False,
            delay=0.5,
            y_offset=-70,
            x_offset=-200,
        )
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
        assistant_force_api = self.root.ai_assistants[self.root.selected_assistant.get()].force_api
        force_api = data if assistant_force_api is None else assistant_force_api
        self.api_name_descr.set(
            f"Selected LLM to use based on:\n"
            f"1. Chat settings: '{data}'\n"
            f"2. Assistant force_api setting: '{assistant_force_api}'"
        )
        self.api_name.set(get_llm_type(force_api).value)
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
