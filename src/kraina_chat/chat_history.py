"""Chat history management and user interface components.

This module provides the main chat interface including history management,
user query handling, file operations, and clipboard integration for the
krAIna chat application.
"""

import base64
import functools
import logging
import subprocess
import sys
import tkinter as tk
import webbrowser
from io import BytesIO
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from typing import Dict, Union

from PIL import UnidentifiedImageError
from tiktoken import encoding_for_model, get_encoding
from tkinterdnd2 import DND_FILES, REFUSE_DROP
from tkinterweb import Notebook
from tktooltip import ToolTip

import kraina.libs.klembord as klembord
import kraina_chat.chat_persistence as chat_persistence
import kraina_chat.chat_settings as chat_settings
from kraina.assistants.assistant import ADDITIONAL_TOKENS_PER_MSG, AssistantResp
from kraina.libs.db.controller import LlmMessageType
from kraina.libs.db.model import Conversations
from kraina.libs.utils import (
    IMAGE_DATA_URL_MARKDOWN_RE,
    _convert_data_url_to_file_url,
    grabclipboard,
    prepare_message,
    str_shortening,
    to_md,
)
from kraina_chat.base import APP_EVENTS, HIGHLIGHTER_CSS, LIGHTTHEME
from kraina_chat.chat_history_view import ChatView, HtmlChatView, TextChatView
from kraina_chat.scroll_text import ScrolledText


class FixedNotebook(Notebook):
    """Fixed notebook widget for tab management.

    Provides a workaround for tab selection issues in the TkinterWeb
    notebook widget until the fix is merged in the upstream repository.

    See: https://github.com/Andereoo/TkinterWeb/pull/102
    """

    def select(self, tabId=None):
        """Select a tab by ID or index.

        :param tabId: The tab ID or index to select
        :return: The selected tab ID
        """
        if tabId in self.pages:
            tabId = self.pages.index(tabId)
            return self.notebook.select(tabId)
        else:
            self.notebook.select(tabId)
            return self.transcribe(self.notebook.select())


logger = logging.getLogger(__name__)


class ChatHistory(FixedNotebook):
    """Chat history widget with dual view support.

    Manages both text and HTML-based chat views, handling message routing,
    theme updates, and conversation state management.
    """

    def __init__(self, parent):
        """Initialize the chat history widget.

        Sets up dual view tabs (HTML and text), configures event bindings,
        and initializes color schemes for different message types.

        :param parent: The parent widget containing this chat history
        """
        super().__init__(parent)
        self.root = parent.master
        self.parent = parent

        self.cols = {
            "HUMAN": self.root.get_theme_color("accent"),
            "TOOL": "#DCBF85",
            "AI": self.root.get_theme_color("fg"),
        }

        self.views: Dict[str, ChatView] = {"html": HtmlChatView(self), "text": TextChatView(self)}
        for k, v in self.views.items():
            self.add(v, text=k)
        if chat_persistence.SETTINGS.last_view_id is not None:
            self.select(chat_persistence.SETTINGS.last_view_id)

        self.bind("<<NotebookTabChanged>>", self._view_change)

        self.root.bind_on_event(APP_EVENTS.QUERY_ASSIST_CREATED, self.human_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_ASSISTANT, self.ai_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_OBSERVATION, self.ai_observation)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_TOOL, self.tool_message)
        self.root.bind_on_event(APP_EVENTS.NEW_CHAT, self.new_chat)
        self.root.bind_on_event(APP_EVENTS.LOAD_CHAT, self.load_chat)
        self.root.bind_on_event(APP_EVENTS.UPDATE_THEME, self.update_tags)
        self.root.bind_on_event(APP_EVENTS.UPDATE_CHAT_TITLE, self.update_title)
        self.root.bind_on_event(APP_EVENTS.COPY_TO_CLIPBOARD_CHAT, self.copy_chat)
        self.root.bind_on_event(APP_EVENTS.EXPORT_CHAT, self.export_to_file)
        self.raw_messages = []

    @staticmethod
    def _remove_img_data(msg: str) -> str:
        """Remove image data URLs from message text.

        Replaces image data URLs with a placeholder text to reduce
        message size for storage and processing.

        :param msg: The message text containing potential image data URLs
        :return: Message text with image data URLs replaced
        """
        if msg:
            return IMAGE_DATA_URL_MARKDOWN_RE.sub("generated image cannot be put here because of size", msg)
        return msg

    def update_title(self, conv: Union[Conversations, None]):
        """Update the chat title display.

        Sets the active chat name and description in the UI variables
        based on the provided conversation object.

        :param conv: The conversation object or None for new chats
        """
        if conv:
            name = conv.name if conv.name else f"ID:{conv.conversation_id}"
            descr = ""
            if conv.description:
                descr += conv.description.replace("\n", "") + ", "
            descr += f"id:{conv.conversation_id}, priority:{conv.priority}, active:{conv.active}  "
        else:
            name = "New chat"
            descr = ""
        self.root.setvar("active_chat_name", name)
        self.root.setvar("active_chat_descr", descr)

    def _view_change(self, *args):  # noqa: ARG002
        """Save the selected tab preference to persistence.

        Called when the user switches between HTML and text views.
        """
        chat_persistence.SETTINGS.last_view_id = self.index(self.select())

    def update_tags(self, theme: str):
        """Update all chat views when theme changes.

        Refreshes the styling of all chat views and reloads the current
        conversation to apply the new theme.

        :param theme: The new theme name
        """
        for view in self.views.values():
            view.update_tags(theme)
        if self.root.conv_id:
            self.root.post_event(APP_EVENTS.LOAD_CHAT, self.root.ai_db.get_conversation(self.root.conv_id))
            self.root.post_event(
                APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
                AssistantResp(
                    self.root.conv_id,
                    "not used",
                    self.root.current_assistant.tokens_used(self.root.conv_id),
                ),
            )

    def new_chat(self, *args):
        """Start a new chat session.

        Clears all chat views, resets conversation state, and optionally
        sets the default assistant if configured.
        """
        for view in self.views.values():
            view.new_chat(*args)
        if (
            chat_settings.SETTINGS.default_assistant
            and chat_settings.SETTINGS.default_assistant in self.root.ai_assistants
        ):
            self.root.selected_assistant.set(chat_settings.SETTINGS.default_assistant)
        self.raw_messages = []
        self.root.conv_id = None
        self.root.post_event(APP_EVENTS.UPDATE_CHAT_TITLE, None)

    def load_chat(self, conversation: Conversations):
        """Load an existing conversation into all views.

        Populates all chat views with the messages from the provided
        conversation and updates the UI state accordingly.

        :param conversation: The conversation object to load
        """
        self.raw_messages = []
        for message in conversation.messages:
            self.raw_messages.append([LlmMessageType(message.type).name, self._remove_img_data(message.message)])
        if self.select() != self.views["html"]:
            self.tab(self.views["html"], state=tk.DISABLED)
        for view in reversed(self.views.values()):
            view.load_chat(conversation)
        if self.select() != self.views["html"]:
            self.tab(self.views["html"], state=tk.NORMAL)
        if len([x[0] for x in self.raw_messages if x[0] == "AI"]) >= 2:
            self._describe_chat()
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                self.root.conv_id,
                "not used",
                self.root.current_assistant.tokens_used(self.root.conv_id),
            ),
        )
        self.root.post_event(APP_EVENTS.UPDATE_CHAT_TITLE, conversation)

    def copy_chat(self, conversation: Conversations):
        """Copy conversation content to clipboard.

        Formats the conversation messages for clipboard copying in both
        text and HTML formats, handling different message types appropriately.

        :param conversation: The conversation to copy to clipboard
        """
        # Always use colors from Light Theme
        cols = {
            "HUMAN": self.root.get_theme_color("accent", "sun-valley-light"),
            "TOOL": "#DCBF85",
            "AI": self.root.get_theme_color("fg", "sun-valley-light"),
        }
        to_clip_text = ""
        to_clip_html = ""
        for message in conversation.messages:
            if LlmMessageType(message.type).name == "TOOL":
                to_clip_text += str_shortening(message.message) + "\n\n"
            else:
                to_clip_text += IMAGE_DATA_URL_MARKDOWN_RE.sub(_convert_data_url_to_file_url, message.message) + "\n\n"
            to_clip_html += to_md(
                *prepare_message(
                    message.message,
                    LlmMessageType(message.type).name,
                    str(cols[LlmMessageType(message.type).name]),
                )
            )
        klembord.init()
        if sys.platform == "win32":
            klembord.set(
                {"HTML Format": klembord.wrap_html(to_clip_html), "CF_UNICODETEXT": to_clip_text.encode("utf-16le")}
            )
        else:
            klembord.set({"UTF8_STRING": to_clip_text.encode(), "text/html": to_clip_html.encode()})

    def export_to_file(self, conversation: Conversations):
        """Export conversation to various file formats.

        Allows users to save conversations as text, HTML, or PDF files
        with appropriate formatting and styling.

        :param conversation: The conversation to export
        """
        fn = asksaveasfilename(
            parent=self,
            initialdir=Path(__name__).parent,
            filetypes=(("supported files files", ["*.pdf", "*.html", "*.txt"]),),
        )
        if not fn:
            return
        # Always use colors from Light Theme
        cols = {
            "HUMAN": self.root.get_theme_color("accent", "sun-valley-light"),
            "TOOL": "#DCBF85",
            "AI": self.root.get_theme_color("fg", "sun-valley-light"),
        }
        to_clip_text = ""
        to_clip_html = (
            '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><style>'
            + LIGHTTHEME
            + HIGHLIGHTER_CSS
            + "</style></head><body>"
        )
        for message in conversation.messages:
            if LlmMessageType(message.type).name == "TOOL":
                to_clip_text += str_shortening(message.message) + "\n\n"
            else:
                to_clip_text += IMAGE_DATA_URL_MARKDOWN_RE.sub(_convert_data_url_to_file_url, message.message) + "\n\n"
            to_clip_html += to_md(
                *prepare_message(
                    message.message,
                    LlmMessageType(message.type).name,
                    str(cols[LlmMessageType(message.type).name]),
                )
            )
            to_clip_html += "</body></html>"
        if Path(fn).suffix.lower() in [".txt"]:
            Path(fn).write_text(to_clip_text, encoding="utf-8")
        elif Path(fn).suffix.lower() == ".html":
            Path(fn).write_text(to_clip_html, encoding="utf-8")
        elif Path(fn).suffix.lower() == ".pdf":
            html = Path(fn).with_suffix(".html")
            html.write_text(to_clip_html, encoding="utf-8")
            app = "chrome" if sys.platform[:3] == "win" else "google-chrome"
            cmdline = [
                app,
                "--headless=old",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={Path(fn).resolve()}",
                html.as_uri(),
            ]
            try:
                subprocess.run(cmdline, start_new_session=True)
            except FileNotFoundError:
                err_msg = f"'{app}' not found. Please install Chrome or Chromium browser and add it to PATH variable"
                logger.error(err_msg)
                self.after_idle(messagebox.showerror, "Export to PDF", err_msg)

    def ai_observation(self, message: str):
        """Handle AI observation messages.

        Adds AI observation messages to the raw message list and
        forwards them to all chat views.

        :param message: The AI observation message content
        """
        self.raw_messages.append(["AI", self._remove_img_data(message)])
        for view in self.views.values():
            view.ai_message(message)

    def ai_message(self, message: str):
        """Handle AI response messages.

        Processes AI messages, updates the UI state, and triggers
        chat history updates and description generation.

        :param message: The AI message content
        """
        self.raw_messages.append(["AI", self._remove_img_data(message)])
        for view in self.views.values():
            view.ai_message(message)
        self.root.post_event(APP_EVENTS.UNBLOCK_USER, None)
        self.root.post_event(APP_EVENTS.COPY_TO_CLIPBOARD, message)
        if len([x[0] for x in self.raw_messages if x[0] == "AI"]) == 1:
            # update chat history after first AI response
            self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())
        if len([x[0] for x in self.raw_messages if x[0] == "AI"]) == 2:
            self._describe_chat()

    def human_message(self, message: str):
        """Handle human input messages.

        Processes human messages and forwards them to the AI assistant
        for processing.

        :param message: The human message content
        """
        self.raw_messages.append(["HUMAN", self._remove_img_data(message)])
        for view in self.views.values():
            view.human_message(message)
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, message)

    def tool_message(self, message: str):
        """Handle tool response messages.

        Processes tool messages and displays them in all chat views.

        :param message: The tool message content
        """
        self.raw_messages.append(["TOOL", self._remove_img_data(message)])
        for view in self.views.values():
            view.tool_message(message)

    def _describe_chat(self):
        """Generate chat description using AI.

        Triggers the nameit snippet to automatically generate a description
        for the chat based on the conversation content.
        """
        self.root.post_event(
            APP_EVENTS.DESCRIBE_NEW_CHAT,
            "\n".join([str_shortening(x[1], 512) for x in self.raw_messages if x[0] in ["AI", "HUMAN"]][0:4]),
        )


class UserQuery(ttk.Frame):
    """User query input frame with advanced features.

    Provides a comprehensive input interface for user queries including
    text input, file handling, clipboard integration, and snippet support.
    """

    def __init__(self, parent):
        """Initialize the user query frame.

        Sets up the text input area, buttons, token counting, and
        various event handlers for user interaction.

        :param parent: The parent widget containing this query frame
        """
        super().__init__(parent, height=10)
        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_SNIPPET, self.skill_message)
        self.root.bind_on_event(APP_EVENTS.UNBLOCK_USER, self.unblock)
        self.text = ScrolledText(self, height=5, selectbackground="lightblue", undo=True)
        self.text.bind("<Return>", self._handle_return)
        self.text.bind("<KP_Enter>", self._handle_return)
        self.text.bind("<ButtonRelease-3>", self._snippets_menu)
        self.text.bind("<KeyRelease>", self._show_tokens)
        self.text.bind("<<Paste>>", self._on_paste)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.text.tag_config("IMAGES")
        self.text.tag_bind("IMAGES", "<Button-1>", self._show_image)
        self.text.tag_bind("IMAGES", "<Enter>", self._enter_hyper)
        self.text.tag_bind("IMAGES", "<Leave>", self._leave_hyper)

        self.text.tag_raise("sel")

        f = ttk.Frame(self)
        self.tokens = tk.StringVar(self, "Tokens: 0")
        self.tokens_after_id = None
        self.label_tokens = ttk.Label(f, relief=tk.SUNKEN, textvariable=self.tokens, width=12, anchor=tk.CENTER)
        self.label_tokens.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.BOTH)

        self.pb = ttk.Progressbar(f, orient="horizontal", mode="indeterminate")

        self.send_btn = ttk.Button(f, text="SEND", width=12, command=functools.partial(self.invoke, "assistant"))
        ToolTip(self.send_btn, msg="<Enter> Ask Assistant", follow=False, delay=0.5, x_offset=-200, y_offset=-20)
        self.send_btn.pack(side=tk.RIGHT, padx=2, pady=2)

        self.add_file_btn = ttk.Button(f, text="ADD FILE...", width=12, command=self.add_file)
        ToolTip(self.add_file_btn, msg="<Ins> Ask Assistant", follow=False, delay=0.5, x_offset=-200, y_offset=-20)
        self.add_file_btn.pack(side=tk.RIGHT, padx=2, pady=2)

        f.pack(side=tk.TOP, fill=tk.X)
        self.block_events = 0
        self.drop_target_register(DND_FILES)  # type: ignore
        self.dnd_bind("<<Drop>>", self._dnd_drop)  # type: ignore

    def _enter_hyper(self, event):  # noqa: ARG002
        """Change cursor to hand when hovering over hyperlinks.

        :param event: The mouse enter event object
        """
        self.text.config(cursor="hand2")

    def _leave_hyper(self, event):  # noqa: ARG002
        """Revert cursor to default when leaving hyperlinks.

        :param event: The mouse leave event object
        """
        self.text.config(cursor="")

    def _show_image(self, event):  # noqa: ARG002
        """Display image in web browser when clicked.

        Extracts image identifier from tags and opens the corresponding
        image file in the default web browser.

        :param event: The mouse click event object
        """
        print(self.text.dump(tk.CURRENT, image=False, text=False, tag=True, mark=False, window=False))
        for el in self.text.dump(tk.CURRENT, image=False, text=False, tag=True, mark=False, window=False):
            # [('tagon', 'IMAGES', '3.0'), ('tagon', 'img-931081a4f276e7e1889ce52da2e87f9b', '3.0')]
            if el[0] == "tagon" and "img-" in el[1]:
                webbrowser.open(self.root.images.get_file_uri(el[1]), new=2, autoraise=True)

    def _dnd_drop(self, e):
        """Handle drag and drop file operations.

        Processes dropped files, inserting images directly or adding
        file references for supported document types.

        :param e: The drop event object
        :return: Action result or REFUSE_DROP for unsupported files
        """
        if e.data and Path(e.data).suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
            name = self.root.images.create_from_file(Path(e.data))
            self.text.image_create(tk.END, image=self.root.images[name], name=name)
            self.text.tag_add(name, name)
            self.text.tag_add("IMAGES", name)
            return e.action
        elif e.data and Path(e.data).suffix.lower() in [".pdf", ".txt", ".log", ".md", ".csv"]:
            self.text.insert(tk.END, f"[{Path(e.data).name}]({e.data})\n")
        else:
            return REFUSE_DROP

    def add_file(self):
        """Open file dialog to add files to the query.

        Allows users to select image files for direct insertion or
        document files for reference links.
        """
        fn = askopenfilename(
            parent=self,
            initialdir=Path(__name__).parent,
            filetypes=(
                ("images", ["*.jpg", "*.png", "*.jpeg", "*.bmp"]),
                ("docs", ["*.pdf", "*.txt", "*.log", "*.md", "*.csv"]),
                ("All files", "*.*"),
            ),
        )
        if fn and Path(fn).suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
            name = self.root.images.create_from_file(Path(fn))
            self.text.image_create(tk.END, image=self.root.images[name], name=name)
            self.text.tag_add(name, name)
            self.text.tag_add("IMAGES", name)
        else:
            self.text.insert(tk.END, f"[{Path(fn).name}]({fn})\n")

    def _on_paste(self, *args):  # noqa: ARG002
        """Handle clipboard paste events.

        Attempts to insert images from the clipboard, converting them
        to PNG format and storing them in the image manager.

        :param args: Additional arguments (unused)
        :raises UnidentifiedImageError: If clipboard content is not an image
        """
        try:
            im = grabclipboard()
            if im:
                with BytesIO() as buffer:
                    im.save(buffer, format="PNG")
                    name = self.root.images.create_from_url(
                        "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
                    )
                    self.text.image_create(tk.END, image=self.root.images[name], name=name)
                    self.text.tag_add(name, name)
                    self.text.tag_add("IMAGES", name)
        except UnidentifiedImageError:
            pass

    def _show_tokens(self, *args):  # noqa: ARG002
        """Schedule token count calculation.

        Debounces token counting to avoid excessive calculations
        during rapid text input.
        """

        def _call(text):
            """Calculate token count for the given text.

            :param text: The text to count tokens for
            """
            try:
                enc = encoding_for_model(self.root.current_assistant.model)
            except KeyError:
                enc = get_encoding("cl100k_base")
            self.tokens.set("Tokens: " + str(len(enc.encode(text)) + ADDITIONAL_TOKENS_PER_MSG))
            self.tokens_after_id = None

        if self.tokens_after_id:
            # if _call was scheduled but has not been executed yet (user is writing)
            # cancel the execution
            self.after_cancel(self.tokens_after_id)
        # schedule calculation of tokens with delay
        self.tokens_after_id = self.after(500, _call, self.text.get("1.0", tk.END))

    def invoke(self, entity: str, event=None):  # noqa: ARG002
        """Process user query submission.

        Handles sending queries to either the AI assistant or snippets
        based on the entity parameter.

        :param entity: Target entity ('assistant' or snippet name)
        :param event: The triggering event object
        :return: 'break' to prevent default event handling
        """
        if entity == "assistant":
            query = ""
            for el in self.text.dump("1.0", tk.END, image=True, text=True):
                if el[0] == "text":
                    query += el[1]
                elif el[0] == "image":
                    query += f"![{el[1]}]({self.root.images.get_base64_url(el[1])})"
            self.text.delete("1.0", tk.END)
            self.root.post_event(
                APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
                AssistantResp(
                    None,
                    "not used",
                    self.root.current_assistant.tokens_used(None),
                ),
            )
            self.root.post_event(APP_EVENTS.QUERY_ASSIST_CREATED, query)
        else:
            range_ = (tk.SEL_FIRST, tk.SEL_LAST) if self.text.tag_ranges(tk.SEL) else ("1.0", tk.END)
            query = self.text.get(*range_)
            self.text.delete(*range_)
            self.root.post_event(APP_EVENTS.QUERY_SNIPPET, dict(entity=entity, query=query))
        self.block()
        return "break"  # stop other events associate with bind to execute

    def _snippets_menu(self, event: tk.Event):
        """Display context menu for available snippets.

        Shows a popup menu with all available AI snippets when
        right-clicking in the text area.

        :param event: The right-click event object
        """
        w = tk.Menu(self, tearoff=False)
        w.bind("<FocusOut>", lambda ev: ev.widget.destroy())
        for skill in self.root.ai_snippets.keys():
            w.add_command(label=skill, command=functools.partial(self.invoke, skill))
        try:
            w.tk_popup(event.x_root, event.y_root)
        finally:
            w.grab_release()

    def skill_message(self, data: str):
        """Insert snippet response into the query text.

        Called when a snippet returns a response, inserting it
        at the current cursor position.

        :param data: The snippet response to insert
        """
        self.unblock()
        self.text.insert(self.text.index(tk.INSERT), data)

    def unblock(self, data=None):  # noqa: ARG002
        """Unblock the query interface.

        Decrements the block counter and re-enables input when
        all blocking operations are complete.

        :param data: Additional data (unused)
        """
        self.block_events -= 1
        if self.block_events == 0:
            self.pb.stop()
            self.pb.forget()
            self.send_btn.configure(state=tk.NORMAL)
            self.text.bind("<Return>", self._handle_return)
            self.text.bind("<KP_Enter>", self._handle_return)

    def block(self, data=None):  # noqa: ARG002
        """Block the query interface.

        Increments the block counter and disables input during
        processing operations.

        :param data: Additional data (unused)
        """
        self.block_events += 1
        if str(self.send_btn.config("state")[4]) == tk.NORMAL:
            self.pb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.pb.start(interval=20)
            self.send_btn.configure(state=tk.DISABLED)
            self.text.unbind("<Return>")
            self.text.unbind("<KP_Enter>")

    def _handle_return(self, event):
        """Handle Return and KP_Enter key presses.

        If Shift is pressed, insert a newline, otherwise invoke the assistant.

        :param event: The key event object
        :return: 'break' to prevent default handling or None to allow it
        """
        if event.state & 0x1:  # Check if Shift is pressed (0x1 is the mask for Shift)
            return None  # Allow default behavior (insert newline)
        else:
            return self.invoke("assistant", event)


class ChatFrame(tk.PanedWindow):
    """Main chat interface frame.

    Combines the chat history view and user query interface in a
    resizable paned window layout.
    """

    def __init__(self, parent):
        """Initialize the chat frame.

        Sets up the paned window with chat history and user query
        components, including title display and sash positioning.

        :param parent: The main application window
        """
        super().__init__(parent, orient=tk.VERTICAL, opaqueresize=False, sashpad=2, sashwidth=4)
        self.root = parent

        chat_hist_frame = ttk.Frame()
        chat_title = ttk.Frame(chat_hist_frame)
        active_chat_name = tk.StringVar(self.root, "", "active_chat_name")
        active_chat_descr = tk.StringVar(self.root, "", "active_chat_descr")
        ttk.Label(chat_title, textvariable=active_chat_name, anchor=tk.NW, wraplength=-1).pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, pady=12, padx=4
        )
        ttk.Label(chat_title, textvariable=active_chat_descr, anchor=tk.NE, wraplength=-1).pack(
            side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=12, padx=4
        )
        chat_title.pack(side=tk.TOP, fill=tk.X)
        ChatHistory(chat_hist_frame).pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.add(chat_hist_frame)

        self.userW = UserQuery(self)
        self.add(self.userW)

        def _set_sashpos(event):  # noqa: ARG001
            """Set the sash position from saved settings.

            Restores the saved sash position when the widget is fully
            configured and ready.

            :param event: The configure event object
            """
            # I have no idea how to set sash pos other way.
            # It must be done when the widget is fully updated.
            # Thus, do this one time on Configure event
            self.sash_place(0, 1, chat_persistence.SETTINGS.sashpos_chat)
            self.unbind("<Configure>")

        self.bind("<Configure>", _set_sashpos)
