"""Chat window."""

import abc
import logging
import tkinter as tk
from tkinter import ttk
import webbrowser

from tkinterweb.htmlwidgets import HtmlFrame

from chat.base import DARKTHEME, LIGHTTHEME, HIGHLIGHTER_CSS
from chat.scroll_text import ScrolledText
from libs.db.controller import LlmMessageType
from libs.db.model import Conversations
from libs.utils import str_shortening, to_md, prepare_message, find_hyperlinks, IMAGE_DATA_URL_MARKDOWN_RE

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
        self.root = parent.master.master
        col = self.root.get_theme_color("accent")
        self.tag_config("HUMAN", foreground=col, spacing3=5)
        self.tag_config("HUMAN_prefix", spacing3=5)
        self.tag_config("AI", lmargin1=10, lmargin2=10)
        self.tag_config("AI_prefix")
        self.tag_config("AI_end")
        self.tag_config("TOOL", lmargin1=10, lmargin2=10, foreground="#DCBF85")
        self.tag_config("TOOL_prefix")
        self.tag_config("hyper", foreground=self.root.get_theme_color("accent"), underline=1)
        self.tag_config("IMAGES")
        self.tag_bind("IMAGES", "<Button-1>", self._show_image)
        self.tag_bind("IMAGES", "<Enter>", self._enter_hyper)
        self.tag_bind("IMAGES", "<Leave>", self._leave_hyper)

        self.tag_bind("hyper", "<Enter>", self._enter_hyper)
        self.tag_bind("hyper", "<Leave>", self._leave_hyper)
        self.tag_bind("hyper", "<Button-1>", self._click_hyper)

        self.tag_raise("sel")

    def _enter_hyper(self, event):
        """
        Change the cursor to a hand when hovering over a hyperlink.

        :param event: The event object containing information about the hover event.
        """
        self.config(cursor="hand2")

    def _leave_hyper(self, event):
        """
        Revert the cursor back to default when leaving a hyperlink.

        :param event: The event object containing information about the leave event.
        """
        self.config(cursor="")

    def _click_hyper(self, event):
        """
        Open the hyperlink in a web browser when clicked.

        :param event: The event object containing information about the click event.
        :raises ValueError: If the hyperlink text cannot be retrieved.
        """
        link = self.get(*self.tag_prevrange("hyper", tk.CURRENT))
        if not link:
            raise ValueError("Unable to retrieve the hyperlink text.")
        webbrowser.open(link, new=2, autoraise=True)

    def _show_image(self, event):
        for el in self.dump(tk.CURRENT, image=False, text=False, tag=True, mark=False, window=False):
            # [('tagon', 'IMAGES', '3.0'), ('tagon', 'img-931081a4f276e7e1889ce52da2e87f9b', '3.0')]
            if el[0] == "tagon" and "img-" in el[1]:
                webbrowser.open(self.root.images.get_file_uri(el[1]), new=2, autoraise=True)

    def update_tags(self, theme: str):
        """Update text tags when theme changed."""
        self.tag_config("HUMAN", foreground=self.root.get_theme_color("accent"))

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
        y_pos = self.yview()[1]
        text = str_shortening(text) if tag == "TOOL" else text
        for tt in text.splitlines(keepends=False):
            start_idx = 0
            for m in IMAGE_DATA_URL_MARKDOWN_RE.finditer(tt):
                img_start = m.start(0)
                if img_start > 0:
                    self.insert(tk.END, "", f"{tag}_prefix", *find_hyperlinks(tt[start_idx:img_start], tag))
                start_idx = m.end(0)
                name = self.root.images.create_from_url(m.group("img_data"), m.group("img_name"))
                self.image_create(tk.END, image=self.root.images[name])
                self.tag_add(name, self.root.images[name])
                self.tag_add("IMAGES", self.root.images[name])
                # self.window_create(
                #     tk.END,
                #     window=tk.Label(
                #         self,
                #         image=self.root.images[name],
                #         background=self.root.get_theme_color("accent"),
                #         borderwidth=3,
                #         relief=tk.SUNKEN,
                #     ),
                # )
            self.insert(tk.END, "", f"{tag}_prefix", *find_hyperlinks(tt[start_idx:], tag), "\n", "")
        if tag == "AI":
            self.insert(tk.END, "\n", "AI_end")
        if y_pos == 1.0:
            self.yview(tk.END)

    def new_chat(self, *args):
        """
        Callback on NEW_CHAT event.

        Clear chat and reset conversion ID.

        :return:
        """
        self.delete(1.0, tk.END)

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
        self.bind("<Button-1>", self.left_click, True)

        self.root = parent.master.master
        theme = ttk.Style().theme_use()
        if "dark" in theme:
            self.enable_dark_theme(True, invert_images=False)
            self.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.enable_dark_theme(False, invert_images=False)
            self.html.update_default_style(LIGHTTHEME)

        self.cols = parent.cols

        self._clear()

    def left_click(self, event):
        if self.get_currently_hovered_node_tag() == "img":
            if url := self.get_currently_hovered_node_attribute("src"):
                if url.startswith("https://"):
                    self._open_webbrowser(url)
                    return
            if alt := self.get_currently_hovered_node_attribute("alt"):
                self._open_webbrowser(self.root.images.get_file_uri(alt))
                return

    @staticmethod
    def _open_webbrowser(url):
        webbrowser.open(url, new=2, autoraise=True)

    def _see_end(self):
        self.yview_moveto(1)

    def _clear(self):
        self.html.reset()
        self.load_html("<p></p>")
        self.add_css(HIGHLIGHTER_CSS)

    def update_tags(self, theme: str):
        """Update text tags when theme changed."""
        if "dark" in theme:
            self.enable_dark_theme(True, invert_images=False)
            self.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.enable_dark_theme(False, invert_images=False)
            self.html.update_default_style(LIGHTTHEME)
        self.cols = {
            "HUMAN": self.root.get_theme_color("accent"),
            "TOOL": "#DCBF85",
            "AI": self.root.get_theme_color("fg"),
        }

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
        self.add_html(to_md(*prepare_message(text, tag, str(self.cols[tag]))))
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

        def _to_md(text, tag):
            return to_md(*prepare_message(text, tag, str(self.cols[tag])))

        self._clear()
        self.add_html("<h2>Loading...</h2>")
        self._see_end()
        self.root.update_idletasks()
        if conversation.assistant:
            self.root.selected_assistant.set(conversation.assistant)
        self._clear()
        self.add_html(
            "".join([_to_md(message.message, LlmMessageType(message.type).name) for message in conversation.messages])
        )
        self._see_end()
