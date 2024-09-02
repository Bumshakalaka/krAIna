"""Debug window."""
import collections
import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

import chat.chat_persistence as chat_persistence
from chat.base import get_windows_version
from chat.scroll_text import ScrolledText
from libs.utils import get_func_args

logger = logging.getLogger(__name__)


class LogFilter(logging.Filter):
    """Filter out log messages."""

    def __init__(self):
        super().__init__()

    def filter(self, record: logging.LogRecord):
        if record.name in ["__main__", "IPyCClient", "IPyCHost", "chat.main", "httpx"]:
            return False
        return True


class QueueHandler(logging.Handler):
    """Class to send logging records to a queue."""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        """Store log record in queue."""
        self.log_queue.append(record)


class MacroWindow(tk.Toplevel):
    """Create Macro Window."""

    def __init__(self, parent, macro: Callable):
        super().__init__(parent)
        self.set_title_bar_color()
        self._update_geometry()
        self.root = parent
        self.macro = macro
        self.macro_params = []
        self.macro_thread: threading.Thread = None

        frame = ttk.Frame(self)
        self._always_on_top = tk.BooleanVar(self, True)
        ttk.Checkbutton(
            frame,
            text="Always on top",
            onvalue=True,
            offvalue=False,
            variable=self._always_on_top,
            command=self.always_on_top,
            width=14,
        ).pack(side=tk.LEFT)
        self.level = tk.StringVar()
        combobox = ttk.Combobox(
            frame,
            textvariable=self.level,
            width=10,
            state="readonly",
            values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        )
        combobox.current(1)
        combobox.pack(side=tk.RIGHT)
        ttk.Label(frame, text="Level:", width=10).pack(side=tk.RIGHT)
        frame.pack(side=tk.TOP, fill=tk.X)

        frame = ttk.Frame(self)
        for k, v in get_func_args(macro).items():
            f = ttk.Frame(frame)
            ttk.Label(f, text=k, anchor=tk.NW, width=20).pack(side=tk.LEFT)
            w = ttk.Entry(f)
            self.macro_params.append(w)
            w.insert(tk.END, str(v) if v else "")
            w.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            f.pack(side=tk.TOP, fill=tk.X)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X)
        self.pb = ttk.Progressbar(frame, orient="horizontal", mode="indeterminate")
        self.pb.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.run_btn = ttk.Button(frame, text="RUN", command=self.run_macro)
        self.run_btn.pack(side=tk.BOTTOM, anchor=tk.NW)
        frame.pack(side=tk.TOP, fill=tk.BOTH)

        self.text = ScrolledText(self, height=12)
        tag_settings = dict(elide=True, lmargin2=10)
        self.text.configure(wrap=tk.WORD)
        self.text.tag_config("DEBUG", **tag_settings)
        self.text.tag_config("INFO", **tag_settings)
        self.text.tag_config("WARNING", foreground="orange", **tag_settings)
        self.text.tag_config("ERROR", foreground="red", **tag_settings)
        self.text.tag_config("CRITICAL", foreground="red", underline=True, **tag_settings)
        self.text.tag_raise("sel")

        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        frame = ttk.Frame(self)
        ttk.Label(frame, text="Search:", width=8).pack(side=tk.LEFT)
        self.search = ttk.Entry(frame, validate="all", validatecommand=(self.register(self.find_select_string), "%P"))
        self.search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(frame, text="Clear", width=8, command=lambda: self.text.delete("1.0", tk.END)).pack(side=tk.RIGHT)
        frame.pack(side=tk.TOP, fill=tk.X)

        self.text.insert(tk.END, macro.__doc__ + "\n")

        self.log_queue = collections.deque(maxlen=1000)
        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"))
        self.queue_handler.addFilter(LogFilter())
        self.queue_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self.queue_handler)

        self.always_on_top()
        self.view_selected()

        self.bind("<<ComboboxSelected>>", self.view_selected)
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        self.get_logs()

    def always_on_top(self):
        """Toggle always on top window setting."""
        self.wm_attributes("-topmost", self._always_on_top.get())

    def view_selected(self, event=None):
        """
        Show the logs at certain log level and above.

        :param event:
        :return:
        """
        req_lvl = self.level.get()
        hide = True
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            if level == req_lvl:
                hide = False
            self.text.tag_config(level, elide=hide)
        if event:
            # change logger level to DEBUG or INFO.
            # DO not set higher levels because we would like to have those data later
            # in case of filter change
            self.queue_handler.setLevel(req_lvl if req_lvl == "DEBUG" else "INFO")

    def close_window(self):
        """Callback on Macro Window destroy event."""
        if int(self.geometry().split("x")[0]) > 10:
            chat_persistence.SETTINGS.macro_wnd_geometry = self.geometry()
        logging.getLogger().removeHandler(self.queue_handler)
        self.destroy()

    def run_macro(self):
        """Run the macro."""
        self.run_btn.config(state="disabled")
        self.pb.start(interval=20)

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
                self.macro,
                *[w.get() for w in self.macro_params],
            ),
            daemon=True,
        )
        self.macro_thread.start()
        self.is_macro_running()

    def is_macro_running(self):
        """If macro thread stops, unblock RUN button and stop progress bar."""
        if not self.macro_thread.is_alive():
            self.pb.stop()
            self.run_btn.config(state="normal")
            return
        self.after(200, self.is_macro_running)

    def set_title_bar_color(self):
        """Set background color of title on Windows only."""
        if get_windows_version() == 10:
            import pywinstyles

            theme = ttk.Style(self).theme_use()
            if theme == "dark":
                pywinstyles.apply_style(self, "dark")
            else:
                pywinstyles.apply_style(self, "normal")

            # A hacky way to update the title bar's color on Windows 10 (it doesn't update instantly like on Windows 11)
            self.wm_attributes("-alpha", 0.99)
            self.wm_attributes("-alpha", 1)
        elif get_windows_version() == 11:
            import pywinstyles

            if "dark" in ttk.Style(self).theme_use():
                take_from = "dark"
            else:
                take_from = "light"
            col = str(self.tk.call("set", f"ttk::theme::sv_{take_from}::colors(-bg)"))
            # Set the title bar color to the background color on Windows 11 for better appearance
            pywinstyles.change_header_color(self, col)

    def find_select_string(self, pattern: str) -> bool:
        """
        Find and select pattern in the log.

        :param pattern: tring to find
        :return: Always True as it bind to Entry validate command
        """
        self.text.tag_remove("sel", "1.0", tk.END)
        if not pattern:
            return True
        self.text.mark_set("matchStart", "1.0")
        self.text.mark_set("matchEnd", "1.0")
        self.text.mark_set("searchLimit", tk.END)

        count = tk.IntVar()
        while True:
            index = self.text.search(pattern, "matchEnd", "searchLimit", count=count, regexp=False)
            if index == "":
                break
            if count.get() == 0:
                break  # degenerate pattern which matches zero-length strings
            self.text.mark_set("matchStart", index)
            self.text.mark_set("matchEnd", "%s+%sc" % (index, count.get()))
            self.text.tag_add("sel", "matchStart", "matchEnd")
        return True

    def _update_geometry(self):
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
        """Display formated log record in text widget."""
        msg = self.queue_handler.format(record)
        print(msg)
        print(record.levelname)
        self.text.insert(tk.END, msg + "\n", record.levelname)
        self.text.yview(tk.END)

    def get_logs(self):
        """
        Get all logs from log queue.

        Call periodically.

        :return:
        """
        while True:
            try:
                self.display(self.log_queue.popleft())
            except IndexError as e:
                break
        self.after(100, self.get_logs)
