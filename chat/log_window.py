"""Debug window."""
import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter.filedialog import asksaveasfile
from tkinter.scrolledtext import ScrolledText


logger = logging.getLogger(__name__)


class DbgLogWindow(tk.Toplevel):
    """Create Debug Window."""

    def __init__(self, parent):
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
        ttk.Button(frame, text="Save...", width=8, command=self.save_log).pack(side=tk.RIGHT)
        frame.pack(side=tk.TOP, fill=tk.X)

        self.always_on_top()

        self.bind("<<ComboboxSelected>>", self.view_selected)
        self.bind("<Escape>", self.hide)
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self.view_selected()

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

    def always_on_top(self):
        """Toggle always on top window setting."""
        self.wm_attributes("-topmost", self._always_on_top.get())

    def save_log(self):
        """
        Save all logs in text widget to the file.

        Also, the invisible once.

        :return:
        """
        fd = asksaveasfile(parent=self, mode="w", defaultextension=".log", initialdir=Path(__file__).parent / "..")
        if fd:
            fd.write(self.text.get("1.0", tk.END))

    def hide(self, *args):
        """Hide the window."""
        if self.visible:
            self.withdraw()
            self.visible = False

    def show(self):
        """Show the window."""
        if not self.visible:
            self.visible = True
            self.get_logs()
            self.withdraw()
            self.deiconify()
            self.lift()

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
            self.root.queue_handler.setLevel(req_lvl if req_lvl == "DEBUG" else "INFO")
            print(self.root.queue_handler.level)

    def display(self, record: logging.LogRecord):
        """Display formated log record in text widget."""
        msg = self.root.queue_handler.format(record)
        self.text.insert(tk.END, msg + "\n", record.levelname)
        self.text.yview(tk.END)

    def get_logs(self):
        """
        Get all logs from log queue.

        Call periodically only when the window is visible.

        :return:
        """
        while True:
            try:
                self.display(self.root.log_queue.popleft())
            except IndexError:
                break
        if self.visible:
            self.after(100, self.get_logs)
