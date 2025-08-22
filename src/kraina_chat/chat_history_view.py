"""Chat history view components for the krAIna chat application.

This module provides abstract and concrete implementations of chat history
views, including text-based and HTML-based rendering options.
"""

import abc
import logging
import tkinter as tk
import webbrowser
from tkinter import ttk

from tkinterweb.htmlwidgets import HtmlFrame

from kraina.libs.db.controller import LlmMessageType
from kraina.libs.db.model import Conversations
from kraina.libs.utils import IMAGE_DATA_URL_MARKDOWN_RE, find_hyperlinks, prepare_message, str_shortening, to_md
from kraina_chat.base import DARKTHEME, HIGHLIGHTER_CSS, LIGHTTHEME
from kraina_chat.scroll_text import ScrolledText

logger = logging.getLogger(__name__)


class ChatView(abc.ABC, tk.Widget):
    """Abstract interface for chat history views.

    Defines the contract that all chat view implementations must follow,
    providing methods for updating themes and handling different message types.
    """

    @abc.abstractmethod
    def update_tags(self, theme: str):
        """Update view styling when theme changes.

        :param theme: The new theme name to apply
        """
        raise NotImplementedError

    @abc.abstractmethod
    def ai_message(self, message: str):
        """Add a new AI message to the chat view.

        :param message: The AI message content to display
        """
        raise NotImplementedError

    @abc.abstractmethod
    def human_message(self, message: str):
        """Add a new human message to the chat view.

        :param message: The human message content to display
        """
        raise NotImplementedError

    @abc.abstractmethod
    def tool_message(self, message: str):
        """Add a new tool message to the chat view.

        :param message: The tool message content to display
        """
        raise NotImplementedError

    @abc.abstractmethod
    def new_chat(self, *args):
        """Create a new chat session.

        Clears the current chat view and prepares for a new conversation.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def load_chat(self, conversation: Conversations):
        """Load an existing chat from history.

        :param conversation: The conversation object containing messages to load
        """
        raise NotImplementedError


class TextChatView(ScrolledText, ChatView):
    """Text-based chat history view implementation.

    Provides a scrollable text widget for displaying chat messages with
    syntax highlighting and interactive elements.
    """

    def __init__(self, parent):
        """Initialize the text-based chat history view.

        Sets up text tags for different message types and configures
        interactive elements like hyperlinks and images.

        :param parent: The parent widget containing this chat view
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
        self.tag_config("hyper", foreground=self.root.get_theme_color("accent"), underline=1)  # type: ignore
        self.tag_config("IMAGES")
        self.tag_bind("IMAGES", "<Button-1>", self._show_image)
        self.tag_bind("IMAGES", "<Enter>", self._enter_hyper)
        self.tag_bind("IMAGES", "<Leave>", self._leave_hyper)

        self.tag_bind("hyper", "<Enter>", self._enter_hyper)
        self.tag_bind("hyper", "<Leave>", self._leave_hyper)
        self.tag_bind("hyper", "<Button-1>", self._click_hyper)

        self.tag_raise("sel")

    def _enter_hyper(self, event):  # noqa: ARG002
        """Change cursor to hand when hovering over hyperlinks.

        :param event: The mouse enter event object
        """
        self.config(cursor="hand2")

    def _leave_hyper(self, event):  # noqa: ARG002
        """Revert cursor to default when leaving hyperlinks.

        :param event: The mouse leave event object
        """
        self.config(cursor="")

    def _click_hyper(self, event):  # noqa: ARG002
        """Open hyperlink in web browser when clicked.

        :param event: The mouse click event object
        :raises ValueError: If hyperlink text cannot be retrieved
        """
        link = self.get(*self.tag_prevrange("hyper", tk.CURRENT))
        if not link:
            raise ValueError("Unable to retrieve the hyperlink text.")
        webbrowser.open(link, new=2, autoraise=True)

    def _show_image(self, event):  # noqa: ARG002
        """Display image in web browser when clicked.

        Extracts image identifier from tags and opens the corresponding
        image file in the default web browser.

        :param event: The mouse click event object
        """
        for el in self.dump(tk.CURRENT, image=False, text=False, tag=True, mark=False, window=False):
            # [('tagon', 'IMAGES', '3.0'), ('tagon', 'img-931081a4f276e7e1889ce52da2e87f9b', '3.0')]
            if el[0] == "tagon" and "img-" in el[1]:
                webbrowser.open(self.root.images.get_file_uri(el[1]), new=2, autoraise=True)

    def update_tags(self, theme: str):  # noqa: ARG002
        """Update text tag colors when theme changes.

        :param theme: The new theme name
        """
        self.tag_config("HUMAN", foreground=self.root.get_theme_color("accent"))

    def ai_message(self, message: str):
        """Add AI message to chat view.

        Called when RESP_FROM_ASSISTANT event is received. Inserts the
        AI message with appropriate formatting and scrolls to bottom.

        :param message: The AI message content to display
        """
        if message:
            self._insert_message(message, "AI")

    def human_message(self, message: str):
        """Add human message to chat view.

        Called when QUERY_ASSIST_CREATED event is received. Inserts the
        human message with appropriate formatting.

        :param message: The human message content to display
        """
        self._insert_message(message, "HUMAN")

    def tool_message(self, message: str):
        """Add tool message to chat view.

        Called when RESP_FROM_TOOL event is received. Inserts the tool
        message with appropriate formatting.

        :param message: The tool message content to display
        """
        self._insert_message(message, "TOOL")

    def _insert_message(self, text, tag):
        """Insert formatted message into the text widget.

        Processes the message text, handles images and hyperlinks,
        and applies appropriate text tags for formatting.

        :param text: The message text to insert
        :param tag: The message type tag (AI, HUMAN, TOOL)
        """
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

    def new_chat(self, *args):  # noqa: ARG002
        """Clear chat view for new conversation.

        Removes all content from the text widget to prepare for
        a new chat session.
        """
        self.delete(1.0, tk.END)

    def load_chat(self, conversation: Conversations):
        """Load existing conversation from history.

        Clears current view and loads all messages from the provided
        conversation object with appropriate formatting.

        :param conversation: The conversation object containing messages to load
        """
        self.delete(1.0, tk.END)
        if conversation.assistant:
            self.root.selected_assistant.set(conversation.assistant)
        for message in conversation.messages:
            self._insert_message(message.message, LlmMessageType(message.type).name)


class HtmlChatView(HtmlFrame, ChatView):
    """HTML-based chat history view implementation.

    Provides an HTML-rendered view for displaying chat messages with
    rich formatting, syntax highlighting, and interactive elements.
    """

    def __init__(self, parent):
        """Initialize the HTML-based chat history view.

        Sets up the HTML frame with appropriate styling and event handlers
        for interactive elements like images and links.

        :param parent: The parent widget containing this chat view
        """
        super().__init__(
            parent, messages_enabled=False, horizontal_scrollbar=True, height=15, borderwidth=1, relief=tk.SUNKEN
        )
        self.configure(forms_enabled=False)
        self.configure(objects_enabled=False)
        self.configure(on_link_click=self._open_webbrowser)
        self.bind("<<DoneLoading>>", lambda e: self._see_end())  # noqa: ARG005
        self.bind("<Button-1>", self.left_click, True)

        self.root = parent.master.master
        theme = ttk.Style().theme_use()
        if "dark" in theme:
            self.html.default_style = LIGHTTHEME + DARKTHEME  # type: ignore
            self.html.update_default_style()
        else:
            self.html.default_style = LIGHTTHEME  # type: ignore
            self.html.update_default_style()

        self.cols = parent.cols

        self._clear()

    def left_click(self, event):  # noqa: ARG002
        """Handle left mouse click on HTML elements.

        Checks if the clicked element is an image and opens it
        in the web browser if it's a valid URL or local image.

        :param event: The mouse click event object
        """
        try:
            hovered = self.get_currently_hovered_element()
        except Exception as e:
            logger.error(f"Error getting hovered element: {e}")
            hovered = None
        if hovered and getattr(hovered, "tagName", None) == "img":
            url = hovered.attributes.get("src") if hasattr(hovered, "attributes") else None
            if url and url.startswith("https://"):
                self._open_webbrowser(url)
                return
            alt = hovered.attributes.get("alt") if hasattr(hovered, "attributes") else None
            if alt:
                self._open_webbrowser(self.root.images.get_file_uri(alt))
                return

    @staticmethod
    def _open_webbrowser(url):
        """Open URL in default web browser.

        :param url: The URL to open in the browser
        """
        webbrowser.open(url, new=2, autoraise=True)

    def _see_end(self):
        """Scroll to the bottom of the HTML content."""
        self.yview_moveto(1)

    def _clear(self):
        """Clear the HTML content and reset the view."""
        self.html.reset()
        self.load_html("<p></p>")
        self.add_css(HIGHLIGHTER_CSS)

    def update_tags(self, theme: str):
        """Update HTML styling when theme changes.

        Applies appropriate CSS styles based on the selected theme
        and updates color mappings for different message types.

        :param theme: The new theme name
        """
        if "dark" in theme:
            self.html.default_style = LIGHTTHEME + DARKTHEME  # type: ignore
            self.html.update_default_style()
        else:
            self.html.default_style = LIGHTTHEME  # type: ignore
            self.html.update_default_style()
        self.cols = {
            "HUMAN": self.root.get_theme_color("accent"),
            "TOOL": "#DCBF85",
            "AI": self.root.get_theme_color("fg"),
        }

    def ai_message(self, message: str):
        """Add AI message to HTML chat view.

        Called when RESP_FROM_ASSISTANT event is received. Converts
        the message to HTML and adds it to the view.

        :param message: The AI message content to display
        """
        if message:
            self._insert_message(message, "AI")

    def human_message(self, message: str):
        """Add human message to HTML chat view.

        Called when QUERY_ASSIST_CREATED event is received. Converts
        the message to HTML and adds it to the view.

        :param message: The human message content to display
        """
        self._insert_message(message, "HUMAN")

    def tool_message(self, message: str):
        """Add tool message to HTML chat view.

        Called when RESP_FROM_TOOL event is received. Converts
        the message to HTML and adds it to the view.

        :param message: The tool message content to display
        """
        self._insert_message(message, "TOOL")

    def _insert_message(self, text, tag):
        """Insert formatted message into the HTML view.

        Converts the message text to HTML with appropriate styling
        and adds it to the HTML frame.

        :param text: The message text to insert
        :param tag: The message type tag (AI, HUMAN, TOOL)
        """
        self.add_html(to_md(*prepare_message(text, tag, str(self.cols[tag]))))
        self._see_end()

    def new_chat(self, *args):  # noqa: ARG002
        """Clear HTML chat view for new conversation.

        Resets the HTML content to prepare for a new chat session.
        """
        self._clear()

    def load_chat(self, conversation: Conversations):
        """Load existing conversation into HTML view.

        Clears current view and loads all messages from the provided
        conversation object, converting them to HTML format.

        :param conversation: The conversation object containing messages to load
        """

        def _to_md(text, tag):
            """Convert text to markdown with appropriate styling.

            :param text: The text to convert
            :param tag: The message type tag
            :return: HTML-formatted markdown string
            """
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
