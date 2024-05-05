import queue
import logging
import sys
import threading
import tkinter as tk
from functools import partial
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from ttkthemes import ThemedTk

from assistants.base import Assistants
from menu import Menu
from dotenv import load_dotenv, find_dotenv


class LeftSidebar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        ttk.Button(self, text="NEW CHAT").pack(side=tk.TOP, fill=tk.X)


class ChatFrame(ttk.PanedWindow):
    chat: ScrolledText
    query: ScrolledText

    def __init__(self, parent):
        super().__init__(parent, orient=tk.VERTICAL)
        self.root = parent
        self.chat = ChatHistory(self, parent)
        w = UserQuery(self, parent)
        self.query = w.text
        self.add(self.chat)
        self.add(w)


class ChatHistory(ScrolledText):
    def __init__(self, parent, root):
        super().__init__(parent, height=15)
        self.tag_config("HUMAN", background="SeaGreen1")
        self.tag_config("AI", background="salmon")
        self.root = root
        self.root.bind("<<HumanAsk>>", self.human_message)
        self.root.bind("<<AiMsgReady>>", self.ai_message)

    def ai_message(self, event):
        print(f"ai_message: {event}")
        query = app_queue.get()
        self.add(query, "AI")

    def human_message(self, event):
        print(f"human_message: {event}")
        query = app_queue.get()
        self.add(query, "HUMAN")
        app_queue.put(query)
        self.root.event_generate("<<AskAi>>")

    def add(self, text, tag, event=None):
        self.insert(tk.END, f"\n{tag}: {text}", tag)


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
        query = self.text.get("1.0", tk.END)
        self.text.delete("1.0", tk.END)
        self.update()
        app_queue.put(query)
        self.root.event_generate("<<HumanAsk>>")
        print("invoke")


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padx=2, pady=2)
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
        self.title("KrAIna CHAT")
        self.set_theme("arc")
        # create menu
        Menu(self)
        pw_main = ttk.PanedWindow(orient=tk.HORIZONTAL)

        left_sidebar = LeftSidebar(self)
        pw_main.add(left_sidebar)

        chat_frame = ChatFrame(self)
        pw_main.add(chat_frame)

        pw_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        StatusBar(self).pack(side=tk.BOTTOM, fill=tk.X)

        self.bind("<<AskAi>>", self.call_assistant)

    def call_assistant(self, event):
        query = app_queue.get()
        tid = threading.Thread(
            target=call_assistant, args=("echo", query, self), daemon=True
        ).start()


def call_assistant(assistant, query, root):
    ret = ai_assistants[assistant].run(query)
    app_queue.put(ret)
    root.event_generate("<<AiMsgReady>>")


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
