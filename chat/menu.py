"""Menu widget"""
import functools
import logging
import subprocess
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox


import chat.chat_persistence as chat_persistence
import chat.chat_settings as chat_settings
from assistants.assistant import AssistantResp
from chat.base import APP_EVENTS
from chat.macro_window import MacroWindow
from libs.llm import overwrite_llm_settings, SUPPORTED_API_TYPE

logger = logging.getLogger(__name__)


class LlmModel(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM model."""
        super().__init__(parent, *args, **kwargs)
        col = parent.get_theme_color("accent")
        self._var = tk.StringVar(self, None)
        self._var.trace("w", self.update_var)
        self.add_radiobutton(label="Default", variable=self._var, value="-", selectcolor=col)
        self.add_radiobutton(label="GPT-3.5-turbo", variable=self._var, value="gpt-3.5-turbo", selectcolor=col)
        self.add_radiobutton(label="GPT-4-turbo", variable=self._var, value="gpt-4-turbo", selectcolor=col)
        self.add_radiobutton(label="GPT-4", variable=self._var, value="gpt-4", selectcolor=col)
        self.add_radiobutton(label="GPT-4o", variable=self._var, value="gpt-4o", selectcolor=col)
        self._var.set("-")

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        overwrite_llm_settings(model="" if _var == "-" else _var)


class LlmTemperature(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM temperature."""
        super().__init__(parent, *args, **kwargs)
        col = parent.get_theme_color("accent")
        self._var = tk.StringVar(self, None)
        self._var.trace("w", self.update_var)
        self.add_radiobutton(label="Default", variable=self._var, value="-", selectcolor=col)
        for t in [0, 0.1, 0.3, 0.5, 0.7, 1.0]:
            self.add_radiobutton(label=str(t), variable=self._var, value=t, selectcolor=col)
        self._var.set("-")

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        overwrite_llm_settings(temperature="" if _var == "-" else _var)


class LlmType(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM temperature."""
        super().__init__(parent, *args, **kwargs)
        col = parent.get_theme_color("accent")
        self.parent = parent
        self._var = tk.StringVar(
            self,
            None,
            "selected_api_type",
        )
        self._var.trace("w", self.update_var)
        self.add_radiobutton(label="Default", variable=self._var, value="-", selectcolor=col)
        for model in SUPPORTED_API_TYPE:
            self.add_radiobutton(label=model.name, variable=self._var, value=model.value, selectcolor=col)

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        api_type = "" if _var == "-" else _var
        chat_persistence.SETTINGS.last_api_type = api_type
        overwrite_llm_settings(api_type=api_type)
        self.parent.post_event(APP_EVENTS.UPDATE_STATUS_BAR_API_TYPE, api_type)
        self.parent.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                self.parent.conv_id,
                "not used",
                self.parent.current_assistant.tokens_used(self.parent.conv_id),
            ),
        )


class SettingsMenu(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for quick settings."""
        super().__init__(parent, *args, **kwargs)
        col = parent.get_theme_color("accent")
        self.parent = parent
        self._always_on_top = tk.BooleanVar(self)
        self._always_on_top.trace("w", self.always_on_top)
        self._copy_to_clip = tk.BooleanVar(self)
        self._copy_to_clip.trace("w", self.copy_to_clip)
        self.add_cascade(label="Theme", menu=ThemeSelect(parent, tearoff=0))
        self.add_checkbutton(
            label="Always on top", variable=self._always_on_top, onvalue=True, offvalue=False, selectcolor=col
        )
        self.add_checkbutton(
            label="Copy to clipboard", variable=self._copy_to_clip, onvalue=True, offvalue=False, selectcolor=col
        )
        self.add_separator()
        self.add_command(
            label="Edit config.yaml",
            command=functools.partial(self.edit_file, Path(__name__).parent / "config.yaml"),
        )
        self.add_command(label="Edit .env", command=functools.partial(self.edit_file, Path(__name__).parent / ".env"))
        self.parent.wm_attributes("-topmost", self._always_on_top.get())
        self._copy_to_clip.set(chat_persistence.SETTINGS.copy_to_clipboard)
        self._always_on_top.set(chat_persistence.SETTINGS.always_on_top)

    def always_on_top(self, *args):
        """Change Always on top setting."""
        _var = self.getvar(name=args[0])
        chat_persistence.SETTINGS.always_on_top = _var
        self.parent.wm_attributes("-topmost", _var)

    def copy_to_clip(self, *args):
        """Change Copy to clipboard setting."""
        _var = self.getvar(name=args[0])
        chat_persistence.SETTINGS.copy_to_clipboard = _var

    def edit_file(self, fn: Path):
        """
        Open the web page associated with an AI assistant.

        This method retrieves the name of the AI assistant from the event widget and opens
        all Assistant files.

        :param event: A Tkinter event object containing the widget that triggered the event.
        :return: None
        """
        if chat_settings.SETTINGS.editor:
            if isinstance(chat_settings.SETTINGS.editor, str):
                args = [chat_settings.SETTINGS.editor]
            else:
                args = chat_settings.SETTINGS.editor
            subprocess.Popen(args + [str(fn)], start_new_session=True)
        else:
            webbrowser.open(str(fn), new=2, autoraise=True)


class ThemeSelect(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM temperature."""
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        col = parent.get_theme_color("accent")
        self._var = tk.StringVar(self, None)
        self._var.set(ttk.Style(self).theme_use())
        self._var.trace("w", self.update_var)
        for t in ttk.Style(parent).theme_names():
            self.add_radiobutton(label=str(t), variable=self._var, value=t, selectcolor=col)

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        style = ttk.Style(self.parent)
        style.theme_use(_var)
        if "dark" in _var:
            self.parent.set_title_bar_color("dark")
        else:
            self.parent.set_title_bar_color("light")
        style.configure("Hidden.TButton", foreground=self.parent.get_theme_color("disfg"))
        style.configure("ERROR.TButton", foreground="red")
        style.configure("WORKING.TButton", foreground=self.parent.get_theme_color("accent"))
        chat_persistence.SETTINGS.theme = style.theme_use()
        self.parent.post_event(APP_EVENTS.UPDATE_THEME, style.theme_use())
        self.after(
            1000,
            messagebox.showwarning,
            "Theme changed",
            "Application is fully functional after theme change but can looks ugly.\n\nReset the application to have it looks good",
        )


class LlmMenu(tk.Menu):
    """LLM sub-menu class."""

    def __init__(self, parent, *args, **kwargs):
        """Create menu."""
        super().__init__(parent, *args, **kwargs)
        self.add_cascade(label="Type", menu=LlmType(parent, tearoff=0))
        self.add_cascade(label="Model", menu=LlmModel(parent, tearoff=0))
        self.add_cascade(label="Temperature", menu=LlmTemperature(parent, tearoff=0))


class Menu(tk.Menu):
    """GUI menu."""

    def __init__(self, parent):
        """Create menu."""
        super().__init__(parent, relief=tk.FLAT)
        self.parent = parent
        self.macro_window = None
        parent.config(menu=self)
        self.add_cascade(label="Llm", menu=LlmMenu(parent, tearoff=0))
        self.add_command(label="Macros", command=self.create_macro_window)
        self.add_cascade(label="Settings", menu=SettingsMenu(parent, tearoff=0))

        self.parent.bind_on_event(APP_EVENTS.CREATE_MACRO_WIN, self.create_macro_window)

    def create_macro_window(self, *args):
        """Create a debug window or summon it if it already exists."""
        if not self.macro_window:
            self.macro_window = MacroWindow(self.parent)
        if not self.macro_window.visible:
            self.macro_window.show()
        else:
            self.macro_window.hide()
