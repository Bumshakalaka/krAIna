import enum
import functools
import logging
import queue
import sys
import threading
import tkinter as tk
from collections import defaultdict, namedtuple
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

from dotenv import load_dotenv, find_dotenv
from ttkthemes import ThemedTk

from assistants.base import Assistants
from menu import Menu
from skills.base import Skills

logger = logging.getLogger(__name__)


class LeftSidebar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.master: "App"
        self.root = parent
        ttk.Button(self, text="NEW CHAT").pack(side=tk.TOP, fill=tk.X)

        fr = ttk.LabelFrame(self, text="Assistants", labelanchor="n")
        for assistant in ai_assistants.keys():
            ttk.Radiobutton(
                fr,
                text=assistant,
                variable=self.master.selected_assistant,
                value=assistant,
            ).pack(side=tk.TOP, fill=tk.X)
        ttk.Button(fr, text="RELOAD").pack(side=tk.BOTTOM, fill=tk.X)
        fr.pack(side=tk.BOTTOM, fill=tk.X)


class ChatFrame(ttk.PanedWindow):
    chat: ScrolledText
    query: ScrolledText

    def __init__(self, parent):
        super().__init__(parent, orient=tk.VERTICAL)
        self.root = parent
        self.add(ChatHistory(self))
        self.add(UserQuery(self))


class ChatHistory(ScrolledText):
    def __init__(self, parent):
        super().__init__(parent, height=15)
        self.tag_config("HUMAN", background="SeaGreen1")
        self.tag_config("AI", background="salmon")
        self.tag_raise("sel")
        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.QUERY_ASSIST_CREATED, self.human_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_ASSISTANT, self.ai_message)

    def ai_message(self, data):
        self.add(data, "AI")

    def human_message(self, data):
        self.add(data, "HUMAN")
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, data)

    def add(self, text, tag):
        self.insert(tk.END, f"{tag}: {text}", tag, "\n", "")


class UserQuery(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_SKILL, self.skill_message)
        self.text = ScrolledText(
            self, height=5, selectbackground="lightblue", undo=True
        )
        self.text.bind("<Control-Return>", functools.partial(self.invoke, "assistant"))
        self.text.bind("<ButtonRelease-3>", self.context_menu)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.send_btn = ttk.Button(
            self, text="Send", command=functools.partial(self.invoke, "assistant")
        )
        self.send_btn.pack(side=tk.BOTTOM, anchor=tk.NE)

    def invoke(self, entity, event=None):
        if entity == "assistant":
            query = self.text.get("1.0", tk.END)[:-1]
            self.text.delete("1.0", tk.END)
            self.root.post_event(APP_EVENTS.QUERY_ASSIST_CREATED, query)
        else:
            range_ = (
                (tk.SEL_FIRST, tk.SEL_LAST)
                if self.text.tag_ranges(tk.SEL)
                else ("1.0", tk.END)
            )
            query = self.text.get(*range_)
            self.text.delete(*range_)
            self.root.post_event(
                APP_EVENTS.QUERY_SKILL, dict(entity=entity, query=query)
            )
        return "break"  # stop other events associate with bind to execute

    def context_menu(self, event: tk.Event):
        w = tk.Menu(self, tearoff=False)
        w.bind("<FocusOut>", lambda ev: ev.widget.destroy())
        for skill in ai_skills.keys():
            w.add_command(label=skill, command=functools.partial(self.invoke, skill))
        try:
            w.tk_popup(event.x_root, event.y_root)
        finally:
            w.grab_release()

    def skill_message(self, data):
        self.text.insert(self.text.index(tk.INSERT), data)


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
        self._bind_table = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=1)

        self.title("KrAIna CHAT")
        self.set_theme("arc")
        self.selected_assistant = tk.StringVar(self, list(ai_assistants.keys())[0])

        Menu(self)
        pw_main = ttk.PanedWindow(orient=tk.HORIZONTAL)

        left_sidebar = LeftSidebar(self)
        pw_main.add(left_sidebar)

        chat_frame = ChatFrame(self)
        pw_main.add(chat_frame)

        pw_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        StatusBar(self).pack(side=tk.BOTTOM, fill=tk.X)

        self.bind_on_event(APP_EVENTS.QUERY_TO_ASSISTANT, self.call_assistant)
        self.bind_on_event(APP_EVENTS.QUERY_SKILL, self.call_skill)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )

    def bind_on_event(self, ev: "APP_EVENTS", cmd: Callable):
        self._bind_table[ev].append(self._event(cmd))
        self.bind(ev.value, self._event(cmd))

    def post_event(self, ev: "APP_EVENTS", data):
        if len(self._bind_table[ev]) == 0:
            logger.error(f"{ev} not bind")
            return
        self._event_queue.put(EVENT(ev, data))
        self.event_generate(ev.value, when="tail")
        logger.info(f"Post event={ev.name} with data='{data}'")

    def _event(self, ev_cmd):
        def wrapper(event):
            _data: EVENT = self._event_queue.get()

            ret = ev_cmd(_data.data)
            logger.info(f"React on={_data.event.name} with data='{_data.data}': {ret=}")
            return ret

        return wrapper

    def call_assistant(self, data):
        _call = lambda assistant, query: self.post_event(
            APP_EVENTS.RESP_FROM_ASSISTANT, ai_assistants[assistant].run(query)
        )
        threading.Thread(
            target=_call,
            args=(self.selected_assistant.get(), data),
            daemon=True,
        ).start()

    def call_skill(self, data):
        _call = lambda skill, query: self.post_event(
            APP_EVENTS.RESP_FROM_SKILL, ai_skills[skill].run(query)
        )
        threading.Thread(
            target=_call,
            args=(data["entity"], data["query"]),
            daemon=True,
        ).start()


class APP_EVENTS(enum.Enum):
    QUERY_ASSIST_CREATED = "<<QueryAssistantCreated>>"
    QUERY_TO_ASSISTANT = "<<QueryAssistant>>"
    RESP_FROM_ASSISTANT = "<<AssistantResp>>"
    RESP_FROM_SKILL = "<<SkillResp>>"
    QUERY_SKILL = "<<QuerySkill>>"


EVENT = namedtuple("EVENT", "event data")

if __name__ == "__main__":
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler("chat.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(
        format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler]
    )
    console_handler.setLevel(logging.INFO)
    load_dotenv(find_dotenv())
    ai_assistants = Assistants()
    ai_skills = Skills()
    app = App()
    app.mainloop()
