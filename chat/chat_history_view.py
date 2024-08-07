"""Chat window."""
import abc
import logging
import tkinter as tk
import webbrowser
from tkinter.scrolledtext import ScrolledText

import markdown
from tkinterweb.htmlwidgets import HtmlFrame

from chat.base import DARKTHEME, LIGHTTHEME
from libs.db.controller import LlmMessageType
from libs.db.model import Conversations
from libs.utils import str_shortening

logger = logging.getLogger(__name__)


class ChatView(abc.ABC, tk.Widget):
    """Interface for Chat History views."""

    @abc.abstractmethod
    def update_tags(self, theme: str):
        """Update view on theme change event."""
        raise NotImplementedError

    @abc.abstractmethod
    def ai_message(self, message: str):
        """Add a new AI message."""
        raise NotImplementedError

    @abc.abstractmethod
    def human_message(self, message: str):
        """Add a new HUMAN message."""
        raise NotImplementedError

    @abc.abstractmethod
    def tool_message(self, message: str):
        """Add a new TOOL message."""
        raise NotImplementedError

    @abc.abstractmethod
    def new_chat(self, *args):
        """Create new chat."""
        raise NotImplementedError

    @abc.abstractmethod
    def load_chat(self, conversation: Conversations):
        """Load new chat from history."""
        raise NotImplementedError


class TextChatView(ScrolledText, ChatView):
    """Chat history frame."""

    def __init__(self, parent):
        """
        Initialize the chat history.

        :param parent: Chat frame.
        """
        super().__init__(parent, height=15)
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-accent)")
        self.tag_config("HUMAN", foreground=col, spacing3=5)
        self.tag_config("HUMAN_prefix", spacing3=5)
        self.tag_config("AI", lmargin1=10, lmargin2=10)
        self.tag_config("AI_prefix")
        self.tag_config("AI_end")
        self.tag_config("TOOL", lmargin1=10, lmargin2=10, foreground="#DCBF85")
        self.tag_config("TOOL_prefix")
        self.tag_raise("sel")
        self.root = parent.master.master

    def update_tags(self, theme: str):
        """Update text tags when theme changed."""
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-accent)")
        self.tag_config("HUMAN", foreground=col)

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

    def human_message(self, message: str):
        """
        Callback on QUERY_ASSIST_CREATED event (query LLM sent).

        1. Insert HUMAN message into chat
        2. Post QUERY_TO_ASSISTANT event to trigger LLM to response.

        :param message: Message to add to chat from QUERY_ASSIST_CREATED event
        """
        self._insert_message(message, "HUMAN")
        self.see(tk.END)

    def tool_message(self, message: str):
        """
        Callback on RESP_FROM_TOOL event (tool message).

        1. Insert TOOL message into chat

        :param message: Message to add to chat from RESP_FROM_TOOL event
        """
        self._insert_message(message, "TOOL")

    def _insert_message(self, text, tag):
        text = str_shortening(text) if tag == "TOOL" else text
        for tt in text.splitlines(keepends=False):
            self.insert(tk.END, "", f"{tag}_prefix", tt, tag, "\n", "")
        if tag == "AI":
            self.insert(tk.END, "\n", "AI_end")
        self.see(tk.END)

    def new_chat(self, *args):
        """
        Callback on NEW_CHAT event.

        Clear chat and reset conversion ID.

        :return:
        """
        self.delete(1.0, tk.END)
        self.see(tk.END)

    def load_chat(self, conversation: Conversations):
        """
        Callback on LOAD_CHAT event which is trigger on entry chat click.

        :param conversation: List of messages
        :return:
        """
        self.delete(1.0, tk.END)
        if conversation.assistant:
            self.root.selected_assistant.set(conversation.assistant)
        for message in conversation.messages:
            self._insert_message(message.message, LlmMessageType(message.type).name)
        self.see(tk.END)


class HtmlChatView(HtmlFrame, ChatView):
    """Chat history frame."""

    def __init__(self, parent):
        """
        Initialize the chat history.

        :param parent: Chat frame.
        """
        super().__init__(
            parent, messages_enabled=False, horizontal_scrollbar=True, height=15, borderwidth=1, relief=tk.SUNKEN
        )
        self.enable_forms(False)
        self.enable_objects(False)
        self.on_link_click(self._open_webbrowser)
        self.on_done_loading(self._see_end)
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        if theme == "dark":
            self.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.html.update_default_style(LIGHTTHEME)

        self._clear()
        self.root = parent.master.master

    @staticmethod
    def _open_webbrowser(url):
        webbrowser.open(url, new=2, autoraise=True)

    def _see_end(self):
        self.yview_moveto(1)

    def _clear(self):
        self.html.reset()
        self.load_html("<p></p>")

    def update_tags(self, theme: str):
        """Update text tags when theme changed."""
        if theme == "dark":
            self.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.html.update_default_style(LIGHTTHEME)

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

    def human_message(self, message: str):
        """
        Callback on QUERY_ASSIST_CREATED event (query LLM sent).

        1. Insert HUMAN message into chat
        2. Post QUERY_TO_ASSISTANT event to trigger LLM to response.

        :param message: Message to add to chat from QUERY_ASSIST_CREATED event
        """
        self._insert_message(message, "HUMAN")

    def tool_message(self, message: str):
        """
        Callback on RESP_FROM_TOOL event (tool message).

        1. Insert TOOL message into chat

        :param message: Message to add to chat from RESP_FROM_TOOL event
        """
        self._insert_message(message, "TOOL")

    def _insert_message(self, text, tag):
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        cols = {
            "HUMAN": self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-accent)"),
            "TOOL": "#DCBF85",
            "AI": self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-fg)"),
        }
        text = str_shortening(text) if tag == "TOOL" else text
        m_text = f'<span style="color:{cols[tag]}">'
        if tag == "HUMAN":
            m_text += (
                text.strip()
                + f'\n\n<hr style="height:2px;border-width:0;color:{cols[tag]};background-color:{cols[tag]}">\n'
            )
        elif tag == "TOOL":
            m_text += text
        else:
            m_text += text
            if len([index for index in range(len(text)) if text.startswith("```", index)]) % 2 == 1:
                # situation when LLM give text block in ``` but the ``` are unbalanced
                # it can happen when completion tokens where not enough
                m_text += "\n```"
            # add horizontal line separator
            m_text += f'\n\n<hr style="height:4px;border-width:0;color:{cols[tag]};background-color:{cols[tag]}">'
        m_text += "</span>"
        html = markdown.markdown(
            m_text,
            extensions=[
                "pymdownx.superfences",
                "markdown.extensions.md_in_html",
                "markdown.extensions.tables",
                "nl2br",
                "sane_lists",
            ],
        )
        self.add_html(html)
        self._see_end()

    def new_chat(self, *args):
        """
        Callback on NEW_CHAT event.

        Clear chat and reset conversion ID.

        :return:
        """
        self._clear()

    def load_chat(self, conversation: Conversations):
        """
        Callback on LOAD_CHAT event which is trigger on entry chat click.

        :param conversation: List of messages
        :return:
        """
        self._clear()
        if conversation.assistant:
            self.root.selected_assistant.set(conversation.assistant)
        for message in conversation.messages:
            self._insert_message(message.message, LlmMessageType(message.type).name)
