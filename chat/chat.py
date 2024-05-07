import enum
import functools
import logging
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

from dotenv import load_dotenv, find_dotenv
from ttkthemes import ThemedTk

from assistants.base import Assistants
from menu import Menu


class LeftSidebar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.root = parent
        ttk.Button(self, text="NEW CHAT").pack(side=tk.TOP, fill=tk.X)


class ChatFrame(ttk.PanedWindow):
    chat: ScrolledText
    query: ScrolledText

    def __init__(self, parent):
        super().__init__(parent, orient=tk.VERTICAL)
        self.root = parent
        self.add(ChatHistory(self, parent))
        self.add(UserQuery(self, parent))


class ChatHistory(ScrolledText):
    def __init__(self, parent, root):
        super().__init__(parent, height=15)
        self.tag_config("HUMAN", background="SeaGreen1")
        self.tag_config("AI", background="salmon")
        self.root = root
        self.root.on_event(APP_EVENTS.QUERY_CREATED, self.human_message)
        self.root.on_event(APP_EVENTS.QUERY_RECV, self.ai_message)

    def ai_message(self, data):
        self.add(data, "AI")

    def human_message(self, data):
        self.add(data, "HUMAN")
        self.root.post_event(APP_EVENTS.QUERY_SEND, data)

    def add(self, text, tag):
        self.insert(tk.END, f"{tag}: {text}", tag, "\n", "")


class UserQuery(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent)
        self.root = root
        self.text = ScrolledText(self, height=5)
        self.text.bind("<Control-Return>", self.invoke)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.send_btn = ttk.Button(self, text="Send", command=self.invoke)
        self.send_btn.pack(side=tk.BOTTOM, anchor=tk.NE)

    def invoke(self, event=None):
        query = self.text.get("1.0", tk.END)[:-1]
        self.text.delete("1.0", tk.END)

        self.root.post_event(APP_EVENTS.QUERY_CREATED, query)
        return "break"  # stop other events associate with bind to execute


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padx=2, pady=2)
        self.root = parent
        ttk.Separator(self).pack(side=tk.TOP, fill=tk.X)
        self.variable = tk.StringVar()
        self.label = ttk.Label(
            self,
            relief=tk.SUNKEN,
            textvariable=self.variable,
            width=10,
        )
        self.variable.set("Status Bar")
        self.label.pack(anchor=tk.NE)


class App(ThemedTk):
    """Main application."""

    def __init__(self):
        """Create MVC application."""
        super().__init__()
        self._app_queue = queue.Queue(maxsize=1)

        self.title("KrAIna CHAT")
        self.set_theme("arc")

        Menu(self)
        pw_main = ttk.PanedWindow(orient=tk.HORIZONTAL)

        left_sidebar = LeftSidebar(self)
        pw_main.add(left_sidebar)

        chat_frame = ChatFrame(self)
        pw_main.add(chat_frame)

        pw_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        StatusBar(self).pack(side=tk.BOTTOM, fill=tk.X)

        self.on_event(APP_EVENTS.QUERY_SEND, self.call_assistant)

    def on_event(self, ev: "APP_EVENTS", cmd: Callable):
        self.bind(ev.value, self._event(cmd))

    def post_event(self, ev: "APP_EVENTS", data):
        app_queue.put(data)
        self.event_generate(ev.value, when="tail")

    def _event(self, ev_cmd):
        def wrapper(event):
            _data = app_queue.get()
            print(f"{event=}, {_data=}")
            ret = ev_cmd(_data)
            print(f"{ret=}")
            return ret

        return wrapper

    def call_assistant(self, data):
        threading.Thread(
            target=call_assistant, args=("echo", data, self), daemon=True
        ).start()


def call_assistant(assistant, query, root):
    ret = ai_assistants[assistant].run(query)
    root.post_event(APP_EVENTS.QUERY_RECV, ret)


class APP_EVENTS(enum.Enum):
    QUERY_CREATED = "<<QueryCreated>>"
    QUERY_SEND = "<<QuerySend>>"
    QUERY_RECV = "<<QueryReceived>>"


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler("chat.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(
        format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler]
    )
    console_handler.setLevel(logging.ERROR)
    load_dotenv(find_dotenv())
    ai_assistants = Assistants()
    app_queue = queue.Queue(maxsize=1)
    app = App()
    app.mainloop()
