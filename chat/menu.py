"""Menu widget"""
import logging
import tkinter as tk

import sv_ttk

import chat.chat_settings as chat_settings
from chat.base import APP_EVENTS
from libs.llm import overwrite_llm_settings

logger = logging.getLogger(__name__)


class FileMenu(tk.Menu):
    """File sub-menu class."""

    def __init__(self, parent, *args, **kwargs):
        """Create menu."""
        super().__init__(parent, *args, **kwargs)
        self.add_command(
            label="Settings...",
        )
        self.add_separator()
        self.add_command(label="Exit", command=parent.quit_app)


class LlmModel(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM model."""
        super().__init__(parent, *args, **kwargs)
        self._var = tk.StringVar(self, None)
        self._var.trace("w", self.update_var)
        self.add_radiobutton(label="Default", variable=self._var, value="")
        self.add_radiobutton(label="GPT-3", variable=self._var, value="gpt-3.5-turbo")
        self.add_radiobutton(label="GPT-4", variable=self._var, value="gpt-4-turbo")

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        overwrite_llm_settings(model="" if _var == "-" else _var)


class LlmTemperature(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM temperature."""
        super().__init__(parent, *args, **kwargs)
        self._var = tk.StringVar(self, None)
        self._var.trace("w", self.update_var)
        self.add_radiobutton(label="Default", variable=self._var, value="")
        for t in [0.1, 0.3, 0.5, 0.7, 1.0]:
            self.add_radiobutton(label=str(t), variable=self._var, value=t)

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        overwrite_llm_settings(temperature="" if _var == "-" else _var)


class LlmType(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for LLM temperature."""
        super().__init__(parent, *args, **kwargs)
        self._var = tk.StringVar(self, None)
        self._var.trace("w", self.update_var)
        self.add_radiobutton(label="Default", variable=self._var, value="-")
        self.add_radiobutton(label="Azure", variable=self._var, value="azure")
        self.add_radiobutton(label="OpenAI", variable=self._var, value="openai")

    def update_var(self, *args):
        """Callback on radiobutton change."""
        _var = self.getvar(name=args[0])
        overwrite_llm_settings(api_type="" if _var == "-" else _var)


class SettingsMenu(tk.Menu):
    def __init__(self, parent, *args, **kwargs):
        """Create sub-menu for quick settings."""
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self._always_on_top = tk.BooleanVar(self)
        self._always_on_top.trace("w", self.always_on_top)
        self._light_mode = tk.BooleanVar(self)
        self._light_mode.trace("w", self.light_mode)
        self.add_checkbutton(label="Always on top", variable=self._always_on_top, onvalue=True, offvalue=False)
        self.add_checkbutton(label="Light theme", variable=self._light_mode, onvalue=True, offvalue=False)
        self.parent.wm_attributes("-topmost", self._always_on_top.get())
        self._light_mode.set(True if chat_settings.SETTINGS.theme == "light" else False)
        self._always_on_top.set(chat_settings.SETTINGS.always_on_top)

    def always_on_top(self, *args):
        """Change Always on top setting."""
        _var = self.getvar(name=args[0])
        chat_settings.SETTINGS.always_on_top = _var
        self.parent.wm_attributes("-topmost", _var)

    def light_mode(self, *args):
        """Change Always on top setting."""
        _var = self.getvar(name=args[0])
        if _var:
            sv_ttk.set_theme("light")
        else:
            sv_ttk.set_theme("dark")
        chat_settings.SETTINGS.theme = sv_ttk.get_theme()
        self.parent.post_event(APP_EVENTS.UPDATE_THEME, sv_ttk.get_theme())


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
        parent.config(menu=self)
        self.add_cascade(label="File", menu=FileMenu(parent, tearoff=0))
        self.add_cascade(label="Llm", menu=LlmMenu(parent, tearoff=0))
        self.add_cascade(label="Settings", menu=SettingsMenu(parent, tearoff=0))
