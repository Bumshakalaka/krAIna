"""Chat window."""

import base64
import copy
import functools
import logging
import sys
import tkinter as tk
import webbrowser
from io import BytesIO
from pathlib import Path
from tkinter import ttk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from typing import Dict, Union

import klembord
from PIL import UnidentifiedImageError
from tiktoken import encoding_for_model, get_encoding
from tkinterdnd2 import DND_FILES, REFUSE_DROP
from tktooltip import ToolTip

import chat.chat_persistence as chat_persistence
import chat.chat_settings as chat_settings
from assistants.assistant import AssistantResp, ADDITIONAL_TOKENS_PER_MSG
from chat.base import APP_EVENTS, LIGHTTHEME, HIGHLIGHTER_CSS
from chat.chat_history_view import ChatView, TextChatView, HtmlChatView
from chat.scroll_text import ScrolledText
from libs.db.controller import LlmMessageType
from libs.db.model import Conversations
from libs.utils import (
    str_shortening,
    prepare_message,
    to_md,
    grabclipboard,
    IMAGE_DATA_URL_MARKDOWN_RE,
    _convert_data_url_to_file_url,
)
from tkinterweb import Notebook


class FixedNotebook(Notebook):
    """
    Remove fix after PR: https://github.com/Andereoo/TkinterWeb/pull/102
    """

    def select(self, tabId=None):
        if tabId in self.pages:
            tabId = self.pages.index(tabId)
            return self.notebook.select(tabId)
        else:
            self.notebook.select(tabId)
            return self.transcribe(self.notebook.select())


logger = logging.getLogger(__name__)


class ChatHistory(FixedNotebook):
    """Chat history Widget with two ChatViews: Text and Markdown"""

    def __init__(self, parent):
        """Initialize widget."""
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
        if msg:
            return IMAGE_DATA_URL_MARKDOWN_RE.sub("generated image cannot be put here because of size", msg)
        return msg

    def update_title(self, conv: Union[Conversations, None]):
        """Update chat label title."""
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

    def _view_change(self, *args):
        """Save selected tab into persistence."""
        chat_persistence.SETTINGS.last_view_id = self.index(self.select())

    def update_tags(self, theme: str):
        """Update widgets when theme changed."""
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
        self.root.post_event(APP_EVENTS.UPDATE_CHAT_TITLE, None)

    def load_chat(self, conversation: Conversations):
        """Call view methods."""
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
        fn = asksaveasfilename(
            parent=self,
            initialdir=Path(__file__).parent / "..",
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
            b = copy.deepcopy(webbrowser.get("google-chrome"))
            b.remote_args = [
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={fn}",
                "%action",
                "%s",
            ]
            b.open(str(html))

    def ai_observation(self, message: str):
        """Call view methods."""
        self.raw_messages.append(["AI", self._remove_img_data(message)])
        for view in self.views.values():
            view.ai_message(message)

    def ai_message(self, message: str):
        """Call view methods."""
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
        """Call view methods."""
        self.raw_messages.append(["HUMAN", self._remove_img_data(message)])
        for view in self.views.values():
            view.human_message(message)
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, message)

    def tool_message(self, message: str):
        """Call view methods."""
        self.raw_messages.append(["TOOL", self._remove_img_data(message)])
        for view in self.views.values():
            view.tool_message(message)

    def _describe_chat(self):
        """Call nameit snippet to describe chat after."""
        self.root.post_event(
            APP_EVENTS.DESCRIBE_NEW_CHAT,
            "\n".join([str_shortening(x[1], 512) for x in self.raw_messages if x[0] in ["AI", "HUMAN"]][0:4]),
        )


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
        ToolTip(self.send_btn, msg="<Ctrl+Enter> Ask Assistant", follow=False, delay=0.5, x_offset=-200, y_offset=-20)
        self.send_btn.pack(side=tk.RIGHT, padx=2, pady=2)

        self.add_file_btn = ttk.Button(f, text="ADD FILE...", width=12, command=self.add_file)
        ToolTip(self.add_file_btn, msg="<Ins> Ask Assistant", follow=False, delay=0.5, x_offset=-200, y_offset=-20)
        self.add_file_btn.pack(side=tk.RIGHT, padx=2, pady=2)

        f.pack(side=tk.TOP, fill=tk.X)
        self.block_events = 0
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._dnd_drop)

    def _enter_hyper(self, event):
        """
        Change the cursor to a hand when hovering over a hyperlink.

        :param event: The event object containing information about the hover event.
        """
        self.text.config(cursor="hand2")

    def _leave_hyper(self, event):
        """
        Revert the cursor back to default when leaving a hyperlink.

        :param event: The event object containing information about the leave event.
        """
        self.text.config(cursor="")

    def _show_image(self, event):
        print(self.text.dump(tk.CURRENT, image=False, text=False, tag=True, mark=False, window=False))
        for el in self.text.dump(tk.CURRENT, image=False, text=False, tag=True, mark=False, window=False):
            # [('tagon', 'IMAGES', '3.0'), ('tagon', 'img-931081a4f276e7e1889ce52da2e87f9b', '3.0')]
            if el[0] == "tagon" and "img-" in el[1]:
                webbrowser.open(self.root.images.get_file(el[1]), new=2, autoraise=True)

    def _dnd_drop(self, e):
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
        fn = askopenfilename(
            parent=self,
            initialdir=Path(__file__).parent / "..",
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

    def _on_paste(self, *args):
        """
        Handle the paste event to insert an image from the clipboard.

        This function attempts to grab an image from the clipboard, convert it to a PNG format,
        and insert it into a text widget. The image is encoded in base64 and stored in a
        custom image manager.

        :param args: Additional arguments (unused).
        :return: None
        :raises UnidentifiedImageError: If the clipboard content is not an image.
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

    def _show_tokens(self, *args):
        """Schedule tokens count on every button release of text paste."""

        def _call(text):
            """Calculate the number of tokens per text"""
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
        self.block_events -= 1
        if self.block_events == 0:
            self.pb.stop()
            self.pb.forget()
            self.send_btn.configure(state=tk.NORMAL)
            self.text.bind("<Control-Return>", functools.partial(self.invoke, "assistant"))

    def block(self, data=None):
        self.block_events += 1
        if str(self.send_btn.config("state")[4]) == tk.NORMAL:
            self.pb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.pb.start(interval=20)
            self.send_btn.configure(state=tk.DISABLED)
            self.text.unbind("<Control-Return>")


class ChatFrame(tk.PanedWindow):
    """Right side chat frame."""

    def __init__(self, parent):
        """
        Initialize the chat frame.
        :param parent: Main App
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

        def _set_sashpos(event):
            # I have no idea how to set sash pos other way.
            # It must be done when the widget is fully updated.
            # Thus, do this one time on Configure event
            self.sash_place(0, 1, chat_persistence.SETTINGS.sashpos_chat)
            self.unbind("<Configure>")

        self.bind("<Configure>", _set_sashpos)
