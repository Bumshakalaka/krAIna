"""Debug window for displaying and managing application logs.

This module provides a debug window interface that displays log messages
with different levels, allows filtering by log level, and provides
search and save functionality for log entries.
"""

import logging
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk
from tkinter.filedialog import asksaveasfile

import kraina_chat.chat_persistence as chat_persistence
from kraina.libs.utils import find_hyperlinks
from kraina_chat.base import get_windows_version
from kraina_chat.scroll_text import ScrolledText

logger = logging.getLogger(__name__)


class DbgLogWindow(tk.Toplevel):
    """Debug window for displaying application logs with filtering and search capabilities.

    This class creates a toplevel window that displays log messages from the
    application's logging system. It provides filtering by log level, search
    functionality, and the ability to save logs to files.
    """

    def __init__(self, parent):
        """Initialize the debug log window.

        :param parent: The parent window widget.
        """
        super().__init__(parent)
        self.visible = True
        self.root = parent
        self.hide()

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

        self.text = ScrolledText(self, state="normal", height=12)
        tag_settings = dict(elide=True, lmargin2=10)
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

        frame = ttk.Frame(self)
        ttk.Label(frame, text="Search:", width=8).pack(side=tk.LEFT)
        self.search = ttk.Entry(frame, validate="all", validatecommand=(self.register(self.find_select_string), "%P"))
        self.search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(frame, text="Clear", width=8, command=lambda: self.text.delete("1.0", tk.END)).pack(side=tk.RIGHT)
        ttk.Button(frame, text="Save...", width=8, command=self.save_log).pack(side=tk.RIGHT)
        frame.pack(side=tk.TOP, fill=tk.X)

        self.always_on_top()

        self.bind("<<ComboboxSelected>>", self.view_selected)
        self.bind("<Escape>", self.hide)
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self.view_selected()

    def _enter_hyper(self, event):  # noqa: ARG002
        """Change the cursor to a hand when hovering over a hyperlink.

        :param event: The event object containing information about the hover event.
        """
        self.text.config(cursor="hand2")

    def _leave_hyper(self, event):  # noqa: ARG002
        """Revert the cursor back to default when leaving a hyperlink.

        :param event: The event object containing information about the leave event.
        """
        self.text.config(cursor="")

    def _click_hyper(self, event):  # noqa: ARG002
        """Open the hyperlink in a web browser when clicked.

        :param event: The event object containing information about the click event.
        :raises ValueError: If the hyperlink text cannot be retrieved.
        """
        link = self.text.get(*self.text.tag_prevrange("hyper", tk.CURRENT))
        if not link:
            raise ValueError("Unable to retrieve the hyperlink text.")
        webbrowser.open(link, new=2, autoraise=True)

    def set_title_bar_color(self):
        """Set background color of title bar on Windows systems.

        This method applies Windows-specific styling to the title bar
        based on the current theme (dark or light mode).
        """
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

    def find_select_string(self, pattern: str) -> bool:
        """Find and select pattern in the log text.

        :param pattern: String pattern to find in the log text.
        :return: Always True as it is bound to Entry validate command.
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

    def always_on_top(self):
        """Toggle always on top window setting.

        Sets or unsets the window's topmost attribute based on the
        checkbox state.
        """
        self.wm_attributes("-topmost", self._always_on_top.get())

    def save_log(self):
        """Save all logs in text widget to a file.

        Opens a file dialog to save the current log content to a .log file.
        The file is saved in the parent directory of this module by default.
        """
        fd = asksaveasfile(parent=self, mode="w", defaultextension=".log", initialdir=Path(__name__).parent)
        if fd:
            fd.write(self.text.get("1.0", tk.END))

    def hide(self, *args):  # noqa: ARG002
        """Hide the debug window.

        Saves the current window geometry before hiding and withdraws
        the window from display.

        :param args: Variable arguments (unused).
        """
        if self.visible:
            if int(self.geometry().split("x")[0]) > 10:
                chat_persistence.SETTINGS.dbg_wnd_geometry = self.geometry()
            self.withdraw()
            self.visible = False

    def show(self):
        """Show the debug window.

        Restores the window geometry, sets title bar color, retrieves
        logs, and makes the window visible.
        """
        if not self.visible:
            self.visible = True
            self.set_title_bar_color()
            self.get_logs()
            self._update_geometry()
            self.withdraw()
            self.deiconify()
            self.lift()

    def _update_geometry(self):
        """Update window geometry and ensure it's within screen bounds.

        Prevents the chat window from being positioned outside the
        visible screen area by resetting to default coordinates if needed.
        """
        # Prevent that chat will always be visible
        w_size, offset_x, offset_y = chat_persistence.SETTINGS.dbg_wnd_geometry.split("+")
        if int(offset_x) > self.winfo_screenwidth() or int(offset_y) > self.winfo_screenheight():
            chat_persistence.SETTINGS.dbg_wnd_geometry = "708x546+0+0"
        elif (
            int(w_size.split("x")[0]) > self.winfo_screenwidth()
            or int(w_size.split("x")[1]) > self.winfo_screenheight()
        ):
            chat_persistence.SETTINGS.dbg_wnd_geometry = "708x546+0+0"
        self.wm_geometry(chat_persistence.SETTINGS.dbg_wnd_geometry)

    def view_selected(self, event=None):
        """Show logs at the selected log level and above.

        Filters the displayed log messages based on the selected log level
        from the combobox. Also updates the logger level for new messages.

        :param event: The combobox selection event (optional).
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
            self.root.queue_handler.setLevel(req_lvl if req_lvl == "DEBUG" else "INFO")

    def display(self, record: logging.LogRecord):
        """Display formatted log record in the text widget.

        Inserts a formatted log message into the text widget with appropriate
        styling based on the log level. Automatically scrolls to the bottom
        if the user was already at the bottom.

        :param record: The log record to display.
        """
        y_pos = self.text.yview()[1]
        msg = self.root.queue_handler.format(record)
        self.text.insert(tk.END, *find_hyperlinks(msg + "\n", record.levelname))
        if y_pos == 1.0:
            self.text.yview(tk.END)

    def get_logs(self):
        """Get all logs from the log queue.

        Retrieves and displays all pending log messages from the queue.
        Schedules itself to run again after 100ms if the window is visible.

        This method should only be called periodically when the window
        is visible to avoid unnecessary processing.
        """
        while True:
            try:
                self.display(self.root.log_queue.popleft())
            except IndexError:
                break
        if self.visible:
            self.after(100, self.get_logs)
