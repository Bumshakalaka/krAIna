"""Chat window."""
import functools
import logging
import tkinter as tk
import webbrowser
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from tkinterweb.htmlwidgets import HtmlFrame
import markdown
from tktooltip import ToolTip

from chat.base import APP_EVENTS, DARKTHEME, LIGHTTHEME
import chat.chat_settings as chat_settings
from libs.db.controller import LlmMessageType
from libs.db.model import Conversations
from libs.utils import str_shortening

logger = logging.getLogger(__name__)


class ChatHistoryHtml(HtmlFrame):
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
        self.on_link_click(self.open_webbrowser)
        self.on_done_loading(self.see_end)
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        if theme == "dark":
            self.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.html.update_default_style(LIGHTTHEME)

        self.root = parent.master
        self.root.bind_on_event(APP_EVENTS.QUERY_ASSIST_CREATED, self.human_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_ASSISTANT, self.ai_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_TOOL, self.tool_message)
        self.root.bind_on_event(APP_EVENTS.NEW_CHAT, self.new_chat)
        self.root.bind_on_event(APP_EVENTS.LOAD_CHAT, self.load_chat)
        self.root.bind_on_event(APP_EVENTS.UPDATE_THEME, self.update_tags)
        self.raw_messages = []

    def open_webbrowser(self, url):
        webbrowser.open(url, new=2, autoraise=True)

    def see_end(self):
        self.yview_moveto(1)

    def clear(self):
        self.load_html("")
        self.raw_messages = []
        self.html.reset()

    def update_tags(self, theme: str):
        """Update text tags when theme changed."""
        if theme == "dark":
            self.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.html.update_default_style(LIGHTTHEME)
        self.root.post_event(APP_EVENTS.LOAD_CHAT, self.root.ai_db.get_conversation(self.root.conv_id))

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
        self.root.post_event(APP_EVENTS.UNBLOCK_USER, None)
        # TODO: make it work with html
        if len([x[0] == "AI" for x in self.raw_messages]) == 2:
            # update chat history after first AI response
            self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, None)
        if len([x[0] == "AI" for x in self.raw_messages]) == 4:
            # call to describe chat after 2 AI messages
            self.root.post_event(
                APP_EVENTS.DESCRIBE_NEW_CHAT,
                "\n".join([x[1] for x in self.raw_messages if x[0] in ["AI", "HUMAN"]][0:3]),
            )

    def human_message(self, message: str):
        """
        Callback on QUERY_ASSIST_CREATED event (query LLM sent).

        1. Insert HUMAN message into chat
        2. Post QUERY_TO_ASSISTANT event to trigger LLM to response.

        :param message: Message to add to chat from QUERY_ASSIST_CREATED event
        """
        self._insert_message(message, "HUMAN")
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, message)

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
        self.raw_messages.append([tag, text])
        m_text = f'<span style="color:{cols[tag]}">'
        if tag == "HUMAN":
            m_text += (
                text + f'\n\n<hr style="height:2px;border-width:0;color:{cols[tag]};background-color:{cols[tag]}">\n'
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

        self.add_html(
            markdown.markdown(
                m_text,
                extensions=["pymdownx.superfences", "markdown.extensions.md_in_html", "markdown.extensions.tables"],
            )
        )

    def new_chat(self, *args):
        """
        Callback on NEW_CHAT event.

        Clear chat and reset conversion ID.

        :return:
        """
        self.clear()
        if (
            chat_settings.SETTINGS.default_assistant
            and chat_settings.SETTINGS.default_assistant in self.root.ai_assistants
        ):
            self.root.selected_assistant.set(chat_settings.SETTINGS.default_assistant)
        self.root.conv_id = None

    def load_chat(self, conversation: Conversations):
        """
        Callback on LOAD_CHAT event which is trigger on entry chat click.

        :param conversation: List of messages
        :return:
        """
        self.clear()
        if conversation.assistant:
            self.root.selected_assistant.set(conversation.assistant)
        for message in conversation.messages:
            self._insert_message(message.message, LlmMessageType(message.type).name)
        if len([x[0] == "AI" for x in self.raw_messages]) == 4:
            self.root.post_event(
                APP_EVENTS.DESCRIBE_NEW_CHAT,
                "\n".join([x[1] for x in self.raw_messages if x[0] in ["AI", "HUMAN"]][0:3]),
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

        self.chatW = ChatHistoryHtml(self)
        self.add(self.chatW)

        self.userW = UserQuery(self)
        self.add(self.userW)
