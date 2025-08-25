"""Status bar widget for the kraina chat application.

This module provides a status bar widget that displays various application states
including API information, token usage, and debug controls.
"""

import logging
import tkinter as tk
from tkinter import ttk

from tktooltip import ToolTip

import kraina_chat.chat_persistence as chat_persistence
from kraina.assistants.assistant import AssistantResp
from kraina.libs.llm import get_llm_type
from kraina_chat.base import APP_EVENTS
from kraina_chat.log_window import DbgLogWindow

logger = logging.getLogger(__name__)


class StatusBar(tk.Frame):
    """Status bar widget displaying application state and controls.

    The status bar shows API information, token usage, and provides access to
    debug and macro windows. It also handles visual feedback for errors and
    running macros.
    """

    def __init__(self, parent):
        """Initialize the status bar widget.

        Args:
            parent: The parent application window.

        """
        super().__init__(parent, padx=2, pady=0)
        self.root = parent
        ttk.Separator(self).pack(side=tk.TOP, fill=tk.X)
        self.token_usage = tk.StringVar()
        self.token_usage_full_str = tk.StringVar()
        self.label_token_usage = ttk.Label(self, relief=tk.FLAT, textvariable=self.token_usage)
        ToolTip(self.label_token_usage, msg=self.token_usage_full_str.get, follow=False, delay=0.5, y_offset=-50)
        self.api_name = tk.StringVar()
        self.api_name_descr = tk.StringVar(
            self,
            f"Selected LLM to use based on:\n"
            f"1. Chat settings: '{chat_persistence.SETTINGS.last_api_type}'\n"
            f"2. Assistant force_api setting: '{self.root.current_assistant.force_api}'",
        )
        self.label_api = ttk.Label(self, relief=tk.FLAT, textvariable=self.api_name, width=10, justify=tk.RIGHT)
        ToolTip(
            self.label_api,
            msg=self.api_name_descr.get,
            follow=False,
            delay=0.5,
            y_offset=-70,
            x_offset=-200,
        )
        self.api_params = tk.StringVar()
        self.label_api_params = ttk.Label(self, relief=tk.FLAT, textvariable=self.api_params)
        self.label_api_params.pack(side=tk.LEFT, fill=tk.BOTH)
        self.label_token_usage.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.dbg_window_btn = ttk.Button(self, text="\u2a00", command=self.create_dbg_window, takefocus=False, width=2)
        ToolTip(
            self.dbg_window_btn,
            msg="Internal logs window\nBlinking red - error in logs",
            follow=False,
            delay=0.5,
            y_offset=-50,
            x_offset=-150,
        )
        self.macro_window_btn = ttk.Button(
            self,
            text="\u2133",
            takefocus=False,
            width=2,
            command=lambda: self.root.post_event(APP_EVENTS.CREATE_MACRO_WIN, None),
        )
        ToolTip(
            self.macro_window_btn,
            msg="Macro window\nHighlighted - Macro is running",
            follow=False,
            delay=0.5,
            y_offset=-50,
            x_offset=-150,
        )
        self.dbg_window_btn.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.macro_window_btn.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.label_api.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.root.bind_on_event(APP_EVENTS.UPDATE_STATUS_BAR_API_TYPE, self.update_statusbar_api)
        self.root.bind_on_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS, lambda data: self.after_idle(self.update_statusbar, data)
        )
        self.root.bind_on_event(APP_EVENTS.WE_HAVE_ERROR, self.blink_start)
        self.root.bind_on_event(APP_EVENTS.MACRO_RUNNING, self.change_macro_status)
        self.blink_after_id = None

    def blink_start(self, data):  # noqa: ARG002
        """Start debug button blinking animation.

        Only starts blinking when the debug window does not exist or is not visible.

        Args:
            data: Event data (unused).

        """
        if self.root.dbg_window and self.root.dbg_window.visible:
            return
        self.blink_stop()
        self.blink_after_id = self.after(300, self.blink)

    def blink_stop(self):
        """Stop debug button blinking animation.

        Cancels the blinking timer and resets button style to default.
        """
        if self.blink_after_id:
            self.after_cancel(self.blink_after_id)
            self.dbg_window_btn.configure(style="")

    def blink(self):
        """Toggle debug button foreground color between red and default.

        Changes the button style every 300ms to create a blinking effect.
        """
        if self.dbg_window_btn.config("style")[4] == "":
            self.dbg_window_btn.configure(style="ERROR.TButton")
        else:
            self.dbg_window_btn.configure(style="")
        self.blink_after_id = self.after(300, self.blink)

    def change_macro_status(self, running):
        """Update macro button visual state based on running status.

        Args:
            running: Boolean indicating if a macro is currently running.

        """
        if running:
            self.macro_window_btn.configure(style="WORKING.TButton")
        else:
            self.macro_window_btn.configure(style="")

    def create_dbg_window(self):
        """Create or toggle debug window visibility.

        Creates a new debug window if none exists, or toggles visibility
        of the existing window. Stops button blinking when called.
        """
        self.blink_stop()
        if not self.root.dbg_window:
            self.root.dbg_window = DbgLogWindow(self.root)
        if not self.root.dbg_window.visible:
            self.root.dbg_window.show()
        else:
            self.root.dbg_window.hide()

    def update_statusbar_api(self, data: str):
        """Update API information display in status bar.

        Updates the API name and description based on chat settings and
        assistant force_api configuration.

        Args:
            data: API type string from chat settings.

        """
        assistant_force_api = self.root.current_assistant.force_api
        force_api = data if assistant_force_api is None else assistant_force_api
        self.api_name_descr.set(
            f"Selected LLM to use based on:\n"
            f"1. Chat settings: '{data}'\n"
            f"2. Assistant force_api setting: '{assistant_force_api}'"
        )
        self.api_name.set(get_llm_type(force_api).value)
        self.label_api.configure(background=self.root.get_theme_color("bg"))

    def update_statusbar(self, data: AssistantResp):
        """Update status bar with token usage or error information.

        Updates the token usage display and handles error states with
        appropriate visual feedback.

        Args:
            data: Assistant response containing token usage or error information.

        """
        if data.error:
            self.token_usage.set(str(data.error)[0:110] + "..." if len(str(data.error)) > 120 else str(data.error))
            self.token_usage_full_str.set(str(data.error))
            # we have error from LLM call
            self.label_token_usage.configure(background="#ED6A5A")
        else:
            self.api_params.set(str(data.tokens.pop("api")) + " | ")
            self.token_usage.set(str(data.tokens))
            self.token_usage_full_str.set(str(data.error))
            self.label_token_usage.configure(background=self.root.get_theme_color("bg"))
