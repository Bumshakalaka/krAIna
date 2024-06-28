"""Chat window."""
import functools
import logging
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict

from tktooltip import ToolTip

import chat.chat_persistence as chat_persistence
import chat.chat_settings as chat_settings
from chat.base import APP_EVENTS
from chat.chat_history_view import ChatView, TextChatView, HtmlChatView
from libs.db.controller import LlmMessageType
from libs.db.model import Conversations

logger = logging.getLogger(__name__)


class ChatHistory(ttk.Notebook):
    """Chat history Widget with two ChatViews: Text and Markdown"""

    def __init__(self, parent):
        """Initialize widget."""
        super().__init__(parent)
        self.root = parent.master
        self.parent = parent

        self.views: Dict[str, ChatView] = {"html": HtmlChatView(self), "text": TextChatView(self)}
        for k, v in self.views.items():
            self.add(v, text=k)
        if chat_persistence.SETTINGS.last_view_id is not None:
            self.select(chat_persistence.SETTINGS.last_view_id)

        self.bind("<<NotebookTabChanged>>", self._view_change)

        self.root.bind_on_event(APP_EVENTS.QUERY_ASSIST_CREATED, self.human_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_ASSISTANT, self.ai_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_TOOL, self.tool_message)
        self.root.bind_on_event(APP_EVENTS.NEW_CHAT, self.new_chat)
        self.root.bind_on_event(APP_EVENTS.LOAD_CHAT, self.load_chat)
        self.root.bind_on_event(APP_EVENTS.UPDATE_THEME, self.update_tags)
        self.raw_messages = []

    def _view_change(self, *args):
        """Save selected tab into persistence."""
        chat_persistence.SETTINGS.last_view_id = self.index(self.select())

    def update_tags(self, theme: str):
        """Update widgets when theme changed."""
        for view in self.views.values():
            view.update_tags(theme)
        self.root.post_event(APP_EVENTS.LOAD_CHAT, self.root.ai_db.get_conversation(self.root.conv_id))

    def new_chat(self, *args):
        """Call view methods."""
        for view in self.views.values():
            view.new_chat(*args)
        if (
            chat_settings.SETTINGS.default_assistant
            and chat_settings.SETTINGS.default_assistant in self.root.ai_assistants
        ):
            self.root.selected_assistant.set(chat_settings.SETTINGS.default_assistant)
        self.raw_messages = []
        self.root.conv_id = None

    def load_chat(self, conversation: Conversations):
        """Call view methods."""
        self.raw_messages = []
        for message in conversation.messages:
            self.raw_messages.append([LlmMessageType(message.type).name, message.message])
        for view in self.views.values():
            view.load_chat(conversation)
        if len([x[0] for x in self.raw_messages if x[0] == "AI"]) >= 2:
            self.root.post_event(
                APP_EVENTS.DESCRIBE_NEW_CHAT,
                "\n".join([x[1] for x in self.raw_messages if x[0] in ["AI", "HUMAN"]][0:3]),
            )

    def ai_message(self, message: str):
        """Call view methods."""
        self.raw_messages.append(["AI", message])
        for view in self.views.values():
            view.ai_message(message)
        self.root.post_event(APP_EVENTS.UNBLOCK_USER, None)

        if len([x[0] for x in self.raw_messages if x[0] == "AI"]) == 1:
            # update chat history after first AI response
            self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, None)
        if len([x[0] for x in self.raw_messages if x[0] == "AI"]) == 2:
            # call to describe chat after 2 AI messages
            self.root.post_event(
                APP_EVENTS.DESCRIBE_NEW_CHAT,
                "\n".join([x[1] for x in self.raw_messages if x[0] in ["AI", "HUMAN"]][0:3]),
            )

    def human_message(self, message: str):
        """Call view methods."""
        self.raw_messages.append(["HUMAN", message])
        for view in self.views.values():
            view.human_message(message)
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, message)

    def tool_message(self, message: str):
        """Call view methods."""
        self.raw_messages.append(["TOOL", message])
        for view in self.views.values():
            view.tool_message(message)


class UserQuery(ttk.Frame):
    """User query frame."""

    def __init__(self, parent):
        """
        Initialize the user query frame.

        :param parent: Chat frame.
        """
        super().__init__(parent, height=10)
        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_SNIPPET, self.skill_message)
        self.root.bind_on_event(APP_EVENTS.UNBLOCK_USER, self.unblock)
        self.text = ScrolledText(self, height=5, selectbackground="lightblue", undo=True)
        self.text.bind("<Control-Return>", functools.partial(self.invoke, "assistant"))
        self.text.bind("<ButtonRelease-3>", self._snippets_menu)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.pb = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
        self.send_btn = ttk.Button(self, text="Send", command=functools.partial(self.invoke, "assistant"))
        ToolTip(self.send_btn, msg="Ask Assistant. <Ctrl+Enter>", follow=False, delay=0.5)
        self.send_btn.pack(side=tk.BOTTOM, anchor=tk.NE, padx=2, pady=2)

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
        for skill in self.root.ai_snippets.keys():
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
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-bg)")
        self.text.configure(state="normal", background=col)

    def block(self, data=None):
        self.pb.pack(side=tk.TOP, fill=tk.X)
        self.pb.start(interval=20)
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-disfg)")
        self.text.configure(state="disabled", background=col)


class ChatFrame(ttk.PanedWindow):
    """Right side chat frame."""

    def __init__(self, parent):
        """
        Initialize the chat frame.
        :param parent: Main App
        """

        super().__init__(parent, orient=tk.VERTICAL)
        self.root = parent

        self.chat_nbk = ChatHistory(self)
        self.add(self.chat_nbk)

        self.userW = UserQuery(self)
        self.add(self.userW)
