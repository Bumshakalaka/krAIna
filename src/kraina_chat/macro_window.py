"""Debug window for managing and running macros with parameter configuration."""

import collections
import copy
import functools
import logging
import subprocess
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk
from typing import Dict, Optional

from tktooltip import ToolTip

import kraina_chat.chat_persistence as chat_persistence
import kraina_chat.chat_settings as chat_settings
from kraina.libs.utils import find_hyperlinks, get_func_args
from kraina.macros.base import Macro, Macros
from kraina_chat.base import APP_EVENTS, get_windows_version
from kraina_chat.scroll_text import ScrolledText

logger = logging.getLogger(__name__)


def dict_merge(existing_dict: dict, new_dict: dict) -> dict:
    """Merge two dictionaries, prioritizing the new dictionary.

    The function performs a deep copy of the new dictionary and updates it with
    values from the existing dictionary if the key is not present in the new dictionary.

    :param existing_dict: The dictionary with existing key-value pairs.
    :param new_dict: The dictionary with new key-value pairs.
    :return: A merged dictionary with updated key-value pairs.
    """
    ret_dict = copy.deepcopy(new_dict)
    for k, v in existing_dict.items():
        if ret_dict.get(k, "\xd7") != "\xd7":
            ret_dict[k] = v
    return ret_dict


class LogFilter(logging.Filter):
    """Filter out specific log messages by name."""

    def __init__(self):
        """Initialize the log filter."""
        super().__init__()

    def filter(self, record: logging.LogRecord):
        """Filter log records based on logger name.

        :param record: The log record to filter.
        :return: False if record should be filtered out, True otherwise.
        """
        if record.name in ["__main__", "IPyCClient", "IPyCHost", "chat.main", "httpx"]:
            return False
        return True


class QueueHandler(logging.Handler):
    """Handler to send logging records to a queue."""

    def __init__(self, log_queue):
        """Initialize the queue handler.

        :param log_queue: The queue to store log records in.
        """
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        """Store log record in the queue.

        :param record: The log record to store.
        """
        self.log_queue.append(record)


class MacroWindow(tk.Toplevel):
    """Main window for managing and running macros with parameter configuration."""

    def __init__(self, parent):
        """Initialize the macro window.

        :param parent: The parent window widget.
        """
        super().__init__(parent)
        self.visible = True
        self.hide()

        self.set_title_bar_color()
        self._update_geometry()
        self.root = parent
        self.macros: Dict[str, Macro] = Macros()
        self.current_macro_name: Optional[str] = None  # type: ignore
        self.macro_thread: Optional[threading.Thread] = None

        self.current_macro_params: Dict[str, Dict] = collections.defaultdict(dict)
        for k, v in self.macros.items():
            self.current_macro_params[k] = get_func_args(v.method)

        # header
        header = ttk.Frame(self)
        self._always_on_top = tk.BooleanVar(self, True)
        ttk.Checkbutton(
            header,
            text="Always on top",
            onvalue=True,
            offvalue=False,
            variable=self._always_on_top,
            command=self.always_on_top,
            width=14,
        ).pack(side=tk.LEFT)
        header.pack(side=tk.TOP, fill=tk.X)
        ###########

        # middle
        middle = ttk.Frame(self)

        middle_left = ttk.Frame(middle)
        self.macro_list_var = tk.Variable(value=list(self.macros.keys()))
        self.macro_list = tk.Listbox(middle_left, width=20, listvariable=self.macro_list_var, selectmode=tk.SINGLE)
        ToolTip(self.macro_list, msg="Right-click to edit macro", follow=False, delay=0.5)
        self.macro_list.bind("<<ListboxSelect>>", self.macro_selected)
        self.macro_list.bind("<Button-3>", self._macro_menu)

        self.macro_list.activate(0)
        self.current_macro_name = self.macro_list.get(0)
        self.macro_list.select_set(0)
        self.macro_list.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        middle_left.pack(side=tk.LEFT, fill=tk.BOTH)

        middle_right = ttk.Frame(middle)

        self.macro_params_frame = ttk.Frame(middle_right)
        self.macro_params_frame.pack(side=tk.TOP, fill=tk.BOTH)

        ttk.Separator(middle, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X, pady=2)

        self.text = ScrolledText(middle_right, height=12)
        tag_settings = dict(lmargin2=10)
        self.text.configure(wrap=tk.WORD)
        self.text.tag_config("DEBUG", **tag_settings)  # type: ignore
        self.text.tag_config("INFO", **tag_settings)  # type: ignore
        self.text.tag_config("WARNING", foreground="orange", **tag_settings)  # type: ignore
        self.text.tag_config("ERROR", foreground="red", **tag_settings)  # type: ignore
        self.text.tag_config("CRITICAL", foreground="red", underline=True, **tag_settings)  # type: ignore
        self.text.tag_config("hyper", foreground=self.root.get_theme_color("accent"), underline=1)  # type: ignore

        self.text.tag_bind("hyper", "<Enter>", self._enter_hyper)
        self.text.tag_bind("hyper", "<Leave>", self._leave_hyper)
        self.text.tag_bind("hyper", "<Button-1>", self._click_hyper)

        self.text.tag_raise("sel")
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        middle_right.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        middle.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # footer
        footer = ttk.Frame(self)
        ttk.Button(footer, text="RELOAD", width=15, command=self.macros_reload).pack(side=tk.LEFT, fill=tk.X)
        self.run_btn = ttk.Button(footer, text="RUN", width=8, command=self.run_macro)
        self.run_btn.pack(side=tk.LEFT)
        self.pb = ttk.Progressbar(footer, orient="horizontal", mode="indeterminate")
        self.pb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(footer, text="Clear", width=8, command=lambda: self.text.delete("1.0", tk.END)).pack(side=tk.LEFT)
        footer.pack(side=tk.TOP, fill=tk.BOTH)

        self.log_queue = collections.deque(maxlen=1000)
        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"))
        self.queue_handler.addFilter(LogFilter())
        self.queue_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self.queue_handler)

        self.macro_params_update()

        self.always_on_top()

        self.bind("<Escape>", self.hide)
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self.get_logs()

    def _enter_hyper(self, event):
        """Change the cursor to a hand when hovering over a hyperlink.

        :param event: The event object containing information about the hover event.
        """
        self.text.config(cursor="hand2")

    def _leave_hyper(self, event):
        """Revert the cursor back to default when leaving a hyperlink.

        :param event: The event object containing information about the leave event.
        """
        self.text.config(cursor="")

    def _click_hyper(self, event):
        """Open the hyperlink in a web browser when clicked.

        :param event: The event object containing information about the click event.
        :raises ValueError: If the hyperlink text cannot be retrieved.
        """
        link = self.text.get(*self.text.tag_prevrange("hyper", tk.CURRENT))
        if not link:
            raise ValueError("Unable to retrieve the hyperlink text.")
        webbrowser.open(link, new=2, autoraise=True)

    def _macro_menu(self, event: tk.Event):
        """Handle the macro menu selection event.

        This function clears the current selection, sets the new selection based on the event's y-coordinate,
        updates the current macro name, and calls the necessary functions to update macro parameters and
        edit the selected macro.

        :param event: The Tkinter event object containing information about the menu event.
        """
        self.macro_list.selection_clear(0, tk.END)
        self.macro_list.selection_set(self.macro_list.nearest(event.y))
        self.macro_list.activate(self.macro_list.nearest(event.y))
        idx = self.macro_list.curselection()
        self.current_macro_name: str = event.widget.get(idx)
        self.macro_params_update()
        self.edit_macro(self.macros[self.current_macro_name].path)

    def edit_macro(self, fn: Path):
        """Open the macro file in the specified editor or web browser and prompt for configuration reload.

        This function opens the given macro file in the configured editor or a web browser. It then
        prompts the user to confirm if they have finished editing and if they want to reload the
        application configuration.

        :param fn: The path to the macro file to be edited.
        :raises subprocess.SubprocessError: If there is an issue starting the editor process.
        :raises webbrowser.Error: If there is an issue opening the web browser.
        """
        if chat_settings.SETTINGS.editor:
            if isinstance(chat_settings.SETTINGS.editor, str):
                args = [chat_settings.SETTINGS.editor]
            else:
                args = chat_settings.SETTINGS.editor
            subprocess.Popen(args + [str(fn)], start_new_session=True)
        else:
            webbrowser.open(str(fn), new=2, autoraise=True)

    def macros_reload(self):
        """Reload the macros and update the macro parameters.

        This function deletes the current macros, initializes new macros, and updates the macro
        parameters and the UI elements accordingly.

        :raises KeyError: If a key in `new_params` does not exist in `current_macro_params`.
        """
        del self.macros
        self.macros = Macros()
        cur_idx = self.macro_list.curselection()
        if cur_idx == ():
            cur_idx = (0,)
        cur_macro = self.macro_list.get(cur_idx)  # type: ignore
        self.macro_list.selection_clear(0, tk.END)

        new_params = collections.defaultdict(dict)
        for k, v in self.macros.items():
            new_params[k] = get_func_args(v.method)

        for k in list(self.current_macro_params.keys()):
            if new_params.get(k) is None:
                del self.current_macro_params[k]

        for k, v in new_params.items():
            self.current_macro_params[k] = dict_merge(self.current_macro_params[k], v)

        self.macro_list_var.set(list(self.macros.keys()))
        if cur_idx[0] < len(self.macros.keys()) and cur_macro == self.macro_list.get(cur_idx):  # type: ignore
            self.macro_list.activate(cur_idx)  # type: ignore
            self.current_macro_name = self.macro_list.get(cur_idx)  # type: ignore
            self.macro_list.select_set(cur_idx)  # type: ignore
        else:
            self.macro_list.activate(0)
            self.current_macro_name = self.macro_list.get(0)
            self.macro_list.select_set(0)
        self.macro_params_update()

    def macro_selected(self, event: tk.Event):
        """Handle the event when a macro is selected from the list.

        This function updates the current macro name and refreshes the macro parameters.

        :param event: The event object containing information about the selection.
        """
        idx = event.widget.curselection()
        if idx:
            self.current_macro_name = event.widget.get(idx)
            self.macro_params_update()

    def macro_params_update(self):
        """Update the macro parameters displayed in the UI.

        This function clears the current parameters and populates the UI with the parameters
        of the currently selected macro.
        """
        for n in list(self.macro_params_frame.children.keys()):
            self.macro_params_frame.children[n].destroy()
        for k, v in self.current_macro_params[self.current_macro_name].items():
            f = ttk.Frame(self.macro_params_frame)
            ttk.Label(f, text=k, anchor=tk.NW, width=20).pack(side=tk.LEFT, padx=10)
            w = ttk.Entry(f)
            w.insert(tk.END, str(v) if v else "")
            w.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            f.pack(side=tk.TOP, fill=tk.X)
            w.config(
                validate="key", validatecommand=(self.register(functools.partial(self.macro_params_save, k)), "%P")
            )

        self.text.delete("1.0", tk.END)
        if self.macros.get(self.current_macro_name):
            self.text.insert(tk.END, str(self.macros[self.current_macro_name].method.__doc__) + "\n")

    def macro_params_save(self, param_name, to_save):
        """Save a macro parameter value.

        :param param_name: The name of the parameter to save.
        :param to_save: The value to save for the parameter.
        :return: Always returns True to indicate successful validation.
        """
        self.current_macro_params[self.current_macro_name].update({param_name: to_save})
        return True

    def always_on_top(self):
        """Toggle always on top window setting."""
        self.wm_attributes("-topmost", self._always_on_top.get())

    def hide(self, *args):
        """Hide the window and save its geometry."""
        if self.visible:
            if int(self.geometry().split("x")[0]) > 10:
                chat_persistence.SETTINGS.macro_wnd_geometry = self.geometry()
            self.withdraw()
            self.visible = False

    def show(self):
        """Show the window and restore its state."""
        if not self.visible:
            self.visible = True
            self.set_title_bar_color()
            self.get_logs()
            self._update_geometry()
            self.withdraw()
            self.deiconify()
            self.lift()

    def run_macro(self):
        """Run the currently selected macro with its parameters."""
        self.run_btn.config(state="disabled")
        self.macro_list.config(state="disabled")
        self.pb.start(interval=20)

        self.root.post_event(APP_EVENTS.MACRO_RUNNING, True)

        def _call(_cmd, *args, **kwargs):
            try:
                ret = _cmd(*args, **kwargs)
                logger.info("*" * (len(str(ret)) + 4))
                logger.info("* " + str(ret) + " *")
                logger.info("*" * (len(str(ret)) + 4))
            except Exception as e:
                logger.info("*" * 40)
                logger.exception(e)
                logger.info("*" * 40)

        self.macro_thread = threading.Thread(
            target=_call,
            args=(
                self.macros[self.current_macro_name].method,
                *[v for v in self.current_macro_params[self.current_macro_name].values()],
            ),
            daemon=True,
        )
        self.macro_thread.start()
        self.is_macro_running()

    def is_macro_running(self):
        """Check if macro thread is still running and update UI accordingly."""
        if self.macro_thread and not self.macro_thread.is_alive():
            self.pb.stop()
            self.run_btn.config(state="normal")
            self.macro_list.config(state="normal")

            self.root.post_event(APP_EVENTS.MACRO_RUNNING, False)
            return
        self.after(200, self.is_macro_running)

    def set_title_bar_color(self):
        """Set background color of title bar based on Windows version and theme."""
        if get_windows_version() == 10:
            import pywinstyles  # type: ignore

            theme = ttk.Style(self).theme_use()
            if theme == "dark":
                pywinstyles.apply_style(self, "dark")
            else:
                pywinstyles.apply_style(self, "normal")

            # A hacky way to update the title bar's color on Windows 10 (it doesn't update instantly like on Windows 11)
            self.wm_attributes("-alpha", 0.99)
            self.wm_attributes("-alpha", 1)
        elif get_windows_version() == 11:
            import pywinstyles  # type: ignore

            if "dark" in ttk.Style(self).theme_use():
                take_from = "dark"
            else:
                take_from = "light"
            col = str(self.tk.call("set", f"ttk::theme::sv_{take_from}::colors(-bg)"))
            # Set the title bar color to the background color on Windows 11 for better appearance
            pywinstyles.change_header_color(self, col)

    def _update_geometry(self):
        """Update window geometry and ensure it's within screen bounds."""
        # Prevent that chat will always be visible
        w_size, offset_x, offset_y = chat_persistence.SETTINGS.macro_wnd_geometry.split("+")
        if int(offset_x) > self.winfo_screenwidth() or int(offset_y) > self.winfo_screenheight():
            chat_persistence.SETTINGS.macro_wnd_geometry = "708x546+0+0"
        elif (
            int(w_size.split("x")[0]) > self.winfo_screenwidth()
            or int(w_size.split("x")[1]) > self.winfo_screenheight()
        ):
            chat_persistence.SETTINGS.macro_wnd_geometry = "708x546+0+0"
        self.wm_geometry(chat_persistence.SETTINGS.macro_wnd_geometry)

    def display(self, record: logging.LogRecord):
        """Display formatted log record in text widget.

        :param record: The log record to display.
        """
        y_pos = self.text.yview()[1]
        msg = self.root.queue_handler.format(record)
        self.text.insert(tk.END, *find_hyperlinks(msg + "\n", record.levelname))
        if y_pos == 1.0:
            self.text.yview(tk.END)

    def get_logs(self):
        """Get all logs from log queue and display them.

        Call periodically to update the log display.

        :return: None
        """
        while True:
            try:
                self.display(self.log_queue.popleft())
            except IndexError:
                break
        if self.visible:
            self.after(100, self.get_logs)
