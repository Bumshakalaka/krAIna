"""Chat with LLM."""
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
from typing import Callable, Dict, Union

from dotenv import load_dotenv, find_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from ttkthemes import ThemedTk

from assistants.base import Assistants
from menu import Menu
from skills.base import Skills

logger = logging.getLogger(__name__)


class LeftSidebar(ttk.Frame):
    """Create left sidebar."""

    def __init__(self, parent):
        """
        Initialize the left sidebar.

        :param parent: Main App
        """
        super().__init__(parent)
        self.master: "App"
        self.root = parent
        ttk.Button(self, text="NEW CHAT", command=self.new_chat).pack(
            side=tk.TOP, fill=tk.X
        )

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

    def new_chat(self):
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)


class ChatFrame(ttk.PanedWindow):
    """Right side chat frame."""

    chat: ScrolledText
    query: ScrolledText

    def __init__(self, parent):
        """
        Initialize the chat frame.
        :param parent: Main App
        """
        super().__init__(parent, orient=tk.VERTICAL)
        self.root = parent
        self.add(ChatHistory(self))
        self.add(UserQuery(self))


class ChatHistory(ScrolledText):
    """Chat history frame."""

    def __init__(self, parent):
        """
        Initialize the chat history.

        :param parent: Chat frame.
        """
        super().__init__(parent, height=15)
        self.tag_config("HUMAN", background="SeaGreen1")
        self.tag_config("AI", background="salmon")
        self.tag_config("HUMAN_prefix", background="SeaGreen1")
        self.tag_config("AI_prefix", background="salmon")
        self.tag_raise("sel")
        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.QUERY_ASSIST_CREATED, self.human_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_ASSISTANT, self.ai_message)
        self.root.bind_on_event(APP_EVENTS.NEW_CHAT, self.clear_messages)

    def ai_message(self, data: Dict):
        """
        Insert an AT-tagged message.

        :param data: Message to add to chat history
        """
        self._insert_message(data["query"], "AI")
        self.see(tk.END)

    def human_message(self, data: Dict):
        """
        Insert a HUMAN-tagged message.

        :param data: Message to add to chat history
        """
        self._insert_message(data["query"], "HUMAN")
        data["hist"] = self.get_history()
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, data)

    def _insert_message(self, text, tag):
        self.insert(tk.END, f"{tag}: ", f"{tag}_prefix", text, tag, "\n", "")

    def clear_messages(self, data: str):
        """
        Cleat chat history

        :param data: Not used
        :return:
        """
        self.delete(1.0, tk.END)
        self.see(tk.END)

    def get_history(self) -> list:
        """
        Get chat history understandable for LLM.
        :return: List of AI and HUman messages
        """
        hist = []
        for human_start, ai_start in zip(
            (it := iter(self.tag_ranges("HUMAN"))), (it2 := iter(self.tag_ranges("AI")))
        ):
            hist.append(HumanMessage(self.get(human_start, next(it))))
            hist.append(AIMessage(self.get(ai_start, next(it2))))
        return hist


class UserQuery(ttk.Frame):
    """User query frame."""

    def __init__(self, parent):
        """
        Initialize the user query frame.

        :param parent: Chat frame.
        """
        super().__init__(parent)
        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_SNIPPET, self.skill_message)
        self.text = ScrolledText(
            self, height=5, selectbackground="lightblue", undo=True
        )
        self.text.bind("<Control-Return>", functools.partial(self.invoke, "assistant"))
        self.text.bind("<ButtonRelease-3>", self._snippets_menu)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.send_btn = ttk.Button(
            self, text="Send", command=functools.partial(self.invoke, "assistant")
        )
        self.send_btn.pack(side=tk.BOTTOM, anchor=tk.NE)

    def invoke(self, entity: str, event=None):
        """
        Callback called on send user query.

        It generates virtual event depends on entity parameter

        :param entity: Destination for sending user queries.
                       'assistant' - send to assistant to answer via APP_EVENTS.QUERY_ASSIST_CREATED
                       else - this is snipped, generate APP_EVENTS.QUERY_SNIPPET
        :param event: tk bind Event
        :return:
        """
        if entity == "assistant":
            query = self.text.get("1.0", tk.END)[:-1]
            self.text.delete("1.0", tk.END)
            self.root.post_event(
                APP_EVENTS.QUERY_ASSIST_CREATED, dict(hist=None, query=query)
            )
        else:
            range_ = (
                (tk.SEL_FIRST, tk.SEL_LAST)
                if self.text.tag_ranges(tk.SEL)
                else ("1.0", tk.END)
            )
            query = self.text.get(*range_)
            self.text.delete(*range_)
            self.root.post_event(
                APP_EVENTS.QUERY_SNIPPET, dict(entity=entity, query=query)
            )
        return "break"  # stop other events associate with bind to execute

    def _snippets_menu(self, event: tk.Event):
        w = tk.Menu(self, tearoff=False)
        w.bind("<FocusOut>", lambda ev: ev.widget.destroy())
        for skill in ai_snippets.keys():
            w.add_command(label=skill, command=functools.partial(self.invoke, skill))
        try:
            w.tk_popup(event.x_root, event.y_root)
        finally:
            w.grab_release()

    def skill_message(self, data: str):
        """
        Insert skill message into User query.

        :param data: message to insert
        :return:
        """
        self.text.insert(self.text.index(tk.INSERT), data)


class StatusBar(tk.Frame):
    """Status Bar."""

    def __init__(self, parent):
        """
        Initialize status bar.

        :param parent: main App
        """
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
        """Create application."""
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
        self.bind_on_event(APP_EVENTS.QUERY_SNIPPET, self.call_snippet)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )

    def bind_on_event(self, ev: "APP_EVENTS", cmd: Callable):
        """
        Bind virtual event to callable.

        :param ev: APP_EVENT
        :param cmd: command to execute on event
        :return:
        """
        self._bind_table[ev].append(self._event(cmd))
        self.bind(ev.value, self._event(cmd))

    def post_event(self, ev: "APP_EVENTS", data: Union[str, Dict]):
        """
        Post virtual event with data.

        :param ev: APP_EVENT to post
        :param data: data to pass to bind callable
        :return:
        """
        if len(self._bind_table[ev]) == 0:
            logger.error(f"{ev} not bind")
            return
        self._event_queue.put(EVENT(ev, data))
        self.event_generate(ev.value, when="tail")
        logger.info(f"Post event={ev.name} with data='{data}'")

    def _event(self, ev_cmd):
        def wrapper(event):
            """Decorate bind callable."""
            _data: EVENT = self._event_queue.get()

            ret = ev_cmd(_data.data)
            logger.info(f"React on={_data.event.name} with data='{_data.data}': {ret=}")
            return ret

        return wrapper

    def call_assistant(self, data: Dict):
        """
        Call AI assistant in separate thread.

        Post APP_EVENTS.RESP_FROM_ASSISTANT event when response is ready.

        :param data: Query to be answered by assistant
        :return:
        """
        _call = lambda assistant, query, hist: self.post_event(
            APP_EVENTS.RESP_FROM_ASSISTANT,
            dict(hist=None, query=ai_assistants[assistant].run(query, hist)),
        )
        threading.Thread(
            target=_call,
            args=(self.selected_assistant.get(), data["query"], data["hist"]),
            daemon=True,
        ).start()

    def call_snippet(self, data: Dict):
        """
        Call AI snippet in separate thread to transform data

        Post APP_EVENTS.RESP_FROM_SNIPPET event when response is ready.

        :param data: Dict(entity=snippet name, query=data to transform)
        :return:
        """
        _call = lambda skill, query: self.post_event(
            APP_EVENTS.RESP_FROM_SNIPPET, ai_snippets[skill].run(query)
        )
        threading.Thread(
            target=_call,
            args=(data["entity"], data["query"]),
            daemon=True,
        ).start()


class APP_EVENTS(enum.Enum):
    """
    App events table.
    """

    QUERY_ASSIST_CREATED = "<<QueryAssistantCreated>>"
    QUERY_TO_ASSISTANT = "<<QueryAssistant>>"
    RESP_FROM_ASSISTANT = "<<AssistantResp>>"
    RESP_FROM_SNIPPET = "<<SkillResp>>"
    QUERY_SNIPPET = "<<QuerySkill>>"
    NEW_CHAT = "<<NewChat>>"


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
    ai_snippets = Skills()
    app = App()
    app.mainloop()
