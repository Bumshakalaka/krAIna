"""Chat window."""
import functools
import logging
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Tuple, List

from chat.base import APP_EVENTS, ai_snippets

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
        self.root.bind_on_event(APP_EVENTS.NEW_CHAT, self.new_chat)
        self.root.bind_on_event(APP_EVENTS.LOAD_CHAT, self.load_chat)

    def ai_message(self, message: str):
        """
        Callback on RESP_FROM_ASSISTANT event (LLM response ready).

        1. Insert AI message into chat
        2. Unblock user query window
        3. Post ADD_NEW_CHAT_ENTRY event on first the AI message. This event updates chat history entries

        :param message: Message to add to chat from RESP_FROM_ASSISTANT event
        """
        if message:
            self._insert_message(message, "AI")
            self.see(tk.END)
        self.root.post_event(APP_EVENTS.UNBLOCK_USER, None)
        if len(self.tag_ranges("AI")) == 2:
            # update chat history after first AI response
            self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, None)

    def human_message(self, message: str):
        """
        Callback on QUERY_ASSIST_CREATED event (query LLM sent).

        1. Insert HUMAN message into chat
        2. Post QUERY_TO_ASSISTANT event to trigger LLM to response.

        :param message: Message to add to chat from QUERY_ASSIST_CREATED event
        """
        self._insert_message(message, "HUMAN")
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, message)

    def _insert_message(self, text, tag):
        self.insert(tk.END, f"{tag}: ", f"{tag}_prefix", text, tag, "\n", "")

    def new_chat(self, *args):
        """
        Callback on NEW_CHAT event.

        Clear chat and reset conversion ID.

        :return:
        """
        self.delete(1.0, tk.END)
        self.see(tk.END)
        self.root.conv_id = None

    def load_chat(self, conversation: Tuple[str, str, List[Tuple[bool, str]]]):
        """
        Callback on LOAD_CHAT event which is trigger on entry chat click.

        :param conversation: List of messages
        :return:
        """
        self.delete(1.0, tk.END)
        for message in conversation[2]:
            if message[0]:
                self._insert_message(message[1], "HUMAN")
            else:
                self._insert_message(message[1], "AI")
        self.see(tk.END)

    def undump(self, dump_data):
        """
        Restore chat from dump.

        :param dump_data: Text.dump()
        :return:
        """
        tags = []
        for key, value, index in dump_data:
            if key == "tagon":
                tags.append(value)
            elif key == "tagoff":
                tags.remove(value)
            elif key == "mark":
                self.mark_set(value, index)
            elif key == "text":
                self.insert(index, value, tags)


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
        self.text = ScrolledText(self, height=5, selectbackground="lightblue", undo=True)
        self.text.bind("<Control-Return>", functools.partial(self.invoke, "assistant"))
        self.text.bind("<ButtonRelease-3>", self._snippets_menu)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.pb = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
        self.send_btn = ttk.Button(self, text="Send", command=functools.partial(self.invoke, "assistant"))
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
            self.root.post_event(APP_EVENTS.QUERY_ASSIST_CREATED, query)
        else:
            range_ = (tk.SEL_FIRST, tk.SEL_LAST) if self.text.tag_ranges(tk.SEL) else ("1.0", tk.END)
            query = self.text.get(*range_)
            self.text.delete(*range_)
            self.root.post_event(APP_EVENTS.QUERY_SNIPPET, dict(entity=entity, query=query))
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

    def __init__(self, parent):
        """
        Initialize the chat frame.
        :param parent: Main App
        """
        super().__init__(parent, orient=tk.VERTICAL)
        self.root = parent
        self.chatW = ChatHistory(self)
        self.add(self.chatW)

        self.userW = UserQuery(self)
        self.add(self.userW)
