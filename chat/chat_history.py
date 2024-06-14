"""Chat window."""
import functools
import logging
import tkinter as tk
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


class ChatHistory(ScrolledText):
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
        self.root = parent.master
        self.parent = parent
        self.root.bind_on_event(APP_EVENTS.QUERY_ASSIST_CREATED, self.human_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_ASSISTANT, self.ai_message)
        self.root.bind_on_event(APP_EVENTS.RESP_FROM_TOOL, self.tool_message)
        self.root.bind_on_event(APP_EVENTS.NEW_CHAT, self.new_chat)
        self.root.bind_on_event(APP_EVENTS.LOAD_CHAT, self.load_chat)
        self.root.bind_on_event(APP_EVENTS.UPDATE_THEME, self.update_tags)

    def update_tags(self, theme: str):
        """Update text tags when theme changed."""
        col = self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-accent)")
        self.tag_config("HUMAN", foreground=col)
        if theme == "dark":
            self.parent.html.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.parent.html.html.update_default_style(LIGHTTHEME)
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
            self.see(tk.END)
        self.root.post_event(APP_EVENTS.UNBLOCK_USER, None)
        if len(self.tag_ranges("AI_end")) == 2:
            # update chat history after first AI response
            self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, None)
        if len(self.tag_ranges("AI_end")) == 4:
            self.root.post_event(APP_EVENTS.DESCRIBE_NEW_CHAT, self.get(1.0, tk.END)[0:14000])

    def human_message(self, message: str):
        """
        Callback on QUERY_ASSIST_CREATED event (query LLM sent).

        1. Insert HUMAN message into chat
        2. Post QUERY_TO_ASSISTANT event to trigger LLM to response.

        :param message: Message to add to chat from QUERY_ASSIST_CREATED event
        """
        self._insert_message(message, "HUMAN")
        self.see(tk.END)
        self.root.post_event(APP_EVENTS.QUERY_TO_ASSISTANT, message)

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
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        cols = {
            "HUMAN": self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-accent)"),
            "TOOL": "#DCBF85",
            "AI": self.tk.call("set", f"ttk::theme::sv_{theme}::colors(-fg)"),
        }
        m_text = f'<span style="color:{cols[tag]}">'
        if tag != "AI":
            for tt in text.splitlines(keepends=False):
                m_text += tt + "<br/>\n"
        else:
            m_text += text + "\n\n---\n"
        m_text += "</span>"

        m_html = markdown.markdown(
            m_text, extensions=["pymdownx.superfences", "markdown.extensions.md_in_html", "markdown.extensions.tables"]
        )
        self.parent.html.add_html(m_html)

    def new_chat(self, *args):
        """
        Callback on NEW_CHAT event.

        Clear chat and reset conversion ID.

        :return:
        """
        self.parent.html.load_html("")
        self.delete(1.0, tk.END)
        self.see(tk.END)
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
        self.parent.html.load_html("")
        self.delete(1.0, tk.END)
        if conversation.assistant:
            self.root.selected_assistant.set(conversation.assistant)
        for message in conversation.messages:
            self._insert_message(message.message, LlmMessageType(message.type).name)
        if len(self.tag_ranges("AI_end")) >= 4:
            self.root.post_event(APP_EVENTS.DESCRIBE_NEW_CHAT, self.get(1.0, tk.END)[0:14000])
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

        self.html = HtmlFrame(self, messages_enabled=False, height=30, borderwidth=1, relief=tk.SUNKEN)
        self.html.enable_forms(False)
        self.html.enable_objects(False)
        self.html.on_link_click(lambda url: print(url))
        theme = self.tk.call("ttk::style", "theme", "use").replace("sun-valley-", "")
        if theme == "dark":
            self.html.html.update_default_style(LIGHTTHEME + DARKTHEME)
        else:
            self.html.html.update_default_style(LIGHTTHEME)
        self.add(self.html)

        self.chatW = ChatHistory(self)
        self.add(self.chatW)

        self.userW = UserQuery(self)
        self.add(self.userW)
