"""Chat window."""
import functools
import logging
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict

from langchain_core.messages import AIMessage, HumanMessage

from base import APP_EVENTS, ai_snippets

logger = logging.getLogger(__name__)


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
        self.root.post_event(APP_EVENTS.UNBLOCK_USER, None)

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
        self.root.bind_on_event(APP_EVENTS.UNBLOCK_USER, self.unblock)
        self.text = ScrolledText(
            self, height=5, selectbackground="lightblue", undo=True
        )
        self.text.bind("<Control-Return>", functools.partial(self.invoke, "assistant"))
        self.text.bind("<ButtonRelease-3>", self._snippets_menu)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.pb = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
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
        self.block()
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
        self.unblock()
        self.text.insert(self.text.index(tk.INSERT), data)

    def unblock(self, data=None):
        self.pb.stop()
        self.pb.forget()
        self.text.configure(state="normal", background="white")

    def block(self, data=None):
        self.pb.pack(side=tk.TOP, fill=tk.X)
        self.pb.start(interval=2)
        self.text.configure(state="disabled", background="grey")


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
