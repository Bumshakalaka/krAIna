"""Left Sidebar window."""
import functools
import logging
from pathlib import Path
from tkinter import ttk
import tkinter as tk
from tkinter.simpledialog import Dialog
from typing import List, Dict
from tktooltip import ToolTip

from assistants.assistant import AssistantType, AssistantResp
from chat.base import APP_EVENTS
import chat.chat_persistence as chat_persistence
from chat.scroll_frame import ScrollFrame
from libs.db.model import Conversations

logger = logging.getLogger(__name__)


class ChatSettingsDialog(Dialog):
    """Chat config right-click menu."""

    def __init__(self, parent, title, init_values: Conversations):
        self.e_name = init_values.name
        self.e_description = init_values.description
        self.e_priority = init_values.priority
        self.e_active = init_values.active
        self.conv_id = init_values.conversation_id
        super().__init__(parent, title)
        # code here will be run after destroying Dialog

    def buttonbox(self):
        """Overloaded method to ubind Return to be able to use it in text widget inside."""
        super().buttonbox()
        self.unbind("<Return>")

    def body(self, master):
        """Create body of right-click menu"""
        f = ttk.Frame(master)
        ttk.Label(f, text="name", anchor=tk.NW, width=10).pack(side=tk.LEFT)
        w = ttk.Entry(f)
        w.insert(tk.END, self.e_name)
        self.e_name = w
        self.e_name.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

        f = ttk.Frame(master)
        ttk.Label(f, text="description", anchor=tk.NW, width=10).pack(side=tk.LEFT)
        w = tk.Text(f, height=10, width=40)
        w.insert(tk.END, self.e_description)
        self.e_description = w
        self.e_description.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

        f = ttk.Frame(master)
        ttk.Label(f, text="Priority", anchor=tk.NW, width=10).pack(side=tk.LEFT)
        w = ttk.Entry(f, validate="key", validatecommand=(self.register(self._val_prio), "%P"))
        w.insert(tk.END, str(self.e_priority))
        self.e_priority = w
        self.e_priority.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

        w = tk.BooleanVar(master, value=True)
        w.set(self.e_active)
        self.e_active = w
        f = ttk.Checkbutton(master, text="Active", onvalue=True, offvalue=False, variable=self.e_active)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

    def _val_prio(self, new_value):
        if new_value == "":
            return True
        try:
            int(new_value)
        except ValueError:
            return False
        else:
            return True

    def apply(self):
        action = dict(
            name=self.e_name.get() if self.e_name.get() else None,
            description=self.e_description.get("1.0", tk.END) if self.e_description.get("1.0", tk.END) else None,
            priority=self.e_priority.get() if self.e_priority.get() else 0,
            active=self.e_active.get(),
        )
        self.parent.post_event(APP_EVENTS.MODIFY_CHAT, dict(conv_id=self.conv_id, action=action))


class LeftSidebar(ttk.Frame):
    """Create left sidebar."""

    def __init__(self, parent):
        """
        Initialize the left sidebar.

        :param parent: Main App
        """
        super().__init__(parent)
        self._chat_history_dir = Path(__file__).parent / "../chat_history"
        self.root = parent
        self.root.bind_on_event(APP_EVENTS.UPDATE_SAVED_CHATS, self.list_saved_chats)
        self.root.bind_on_event(APP_EVENTS.UPDATE_AI, self.list_assistsnts)
        but = ttk.Button(self, text="NEW CHAT", command=self.new_chat)
        ToolTip(but, msg="Create new chat", follow=False, delay=0.5)
        but.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        w = ScrollFrame(self, text="Last chats")
        self.chats = w.viewPort
        self.chat_tooltips = []
        w.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.assistants = ttk.LabelFrame(self, text="Assistants", labelanchor="n")
        self.list_assistsnts()
        self.assistants.pack(side=tk.BOTTOM, fill=tk.X)
        but = ttk.Button(self.assistants, text="RELOAD", command=self.reload_ai)
        ToolTip(but, msg="Reload Assistants and Snippets", follow=False, delay=0.5)
        but.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)

    def list_assistsnts(self, *args):
        for n in list(self.assistants.children.keys()):
            if not isinstance(self.assistants.children[n], ttk.Button):
                self.assistants.children[n].destroy()
        for name, assistant in self.root.ai_assistants.items():
            name_ = name if assistant.type == AssistantType.SIMPLE else f"{name}(tools)"
            rbut = ttk.Radiobutton(
                self.assistants,
                text=name_,
                variable=self.root.selected_assistant,
                value=name,
                command=self.assistant_change,
            )
            msg_ = assistant.description if assistant.description else name_
            if assistant.type == AssistantType.WITH_TOOLS:
                tools_ = "\n- " + "\n- ".join(assistant.tools)
                msg_ += f"\nTools:{tools_}"
            ToolTip(rbut, msg=msg_, follow=False, delay=0.5)
            rbut.pack(side=tk.TOP, fill=tk.X)

    def assistant_change(self, *args):
        chat_persistence.SETTINGS.last_assistant = self.root.selected_assistant.get()
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                self.root.conv_id,
                "not used",
                self.root.ai_assistants[self.root.selected_assistant.get()].tokens_used(self.root.conv_id),
            ),
        )
        self.root.post_event(APP_EVENTS.UPDATE_STATUS_BAR_API_TYPE, chat_persistence.SETTINGS.last_api_type)

    def list_saved_chats(self, conversations: List[Conversations]):
        """
        Callback on UPDATE_SAVED_CHATS event.

        Create chat history entries.

        :param conversations: list of the active conversations
        :return:
        """
        self.chats.master.yview_moveto(0.0)  # scroll to the top
        for n in self.chat_tooltips:
            n.destroy()
        for n in list(self.chats.children.keys()):
            self.chats.children[n].destroy()
        separator = False
        self.chat_tooltips = []
        for conversation in conversations:
            if not separator and conversation.priority == 0:
                separator = True
                ttk.Separator(self.chats, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X, pady=10, padx=6)
            name = conversation.name if conversation.name else f"ID:{conversation.conversation_id}"
            but = ttk.Button(
                self.chats,
                text=name,
                command=functools.partial(self.get_chat, conversation.conversation_id),
            )
            # add conversation object to button to have it in right-click menu
            setattr(but, "conversation", conversation)
            if not conversation.active:
                # TODO: Change background color or style of hidden chats somehow
                but.configure(text=f"(H) {but.cget('text')}")
            tooltip_msg = (
                f"id:{conversation.conversation_id}\npriority:{conversation.priority}\nactive:{conversation.active}"
            )
            if conversation.description:
                tooltip_msg = conversation.description.strip() + "\n\n" + tooltip_msg
            self.chat_tooltips.append(ToolTip(but, msg=tooltip_msg, delay=0.5, follow=False))
            but.bind("<ButtonRelease-3>", functools.partial(self._chat_menu, conversation.conversation_id))
            but.pack(side=tk.TOP, fill=tk.X, pady=2, padx=6)

    def _chat_menu(self, conv_id: int, event: tk.Event):
        # event.widget
        w = tk.Menu(self, tearoff=False)
        w.bind("<FocusOut>", lambda ev: ev.widget.destroy())
        pinned = event.widget.conversation.priority
        active = event.widget.conversation.active
        w.add_command(label=f"Chat: {conv_id}", state="disabled")
        w.add_command(
            label=f"{'Pin' if pinned == 0 else 'Unpin'}",
            command=functools.partial(self.pin_unpin_chat, event.widget),
        )
        w.add_command(
            label=f"{'Hide' if active else 'UnHide'}",
            command=functools.partial(self.modify_chat, conv_id, {"active": not active}),
        )
        w.add_command(label=f"Edit...", command=functools.partial(self.edit_chat, event.widget))
        w.add_separator()
        w.add_command(label=f"Delete", command=functools.partial(self.delete_chat, conv_id))
        w.add_separator()
        w.add_command(
            label=f"{'Hide' if chat_persistence.SETTINGS.show_also_hidden_chats else 'UnHide'} Chats",
            command=self.visibility_chats,
        )
        try:
            w.tk_popup(event.x_root, event.y_root)
        finally:
            w.grab_release()

    def pin_unpin_chat(self, w: tk.Widget):
        """Pin (priority=1) or unpin (priority=0) chat"""
        conv: Conversations = w.conversation
        priority = 1
        if conv.priority > 0:
            priority = 0
        self.root.post_event(
            APP_EVENTS.MODIFY_CHAT, dict(conv_id=int(conv.conversation_id), action={"priority": priority})
        )

    def edit_chat(self, w: tk.Widget):
        """SHow Chat settings toplevel to edit name, description, etc."""
        ChatSettingsDialog(self.root, f"{w.conversation.conversation_id} Settings", w.conversation)  # noqa

    def visibility_chats(self):
        """Show all hats or ony active."""
        chat_persistence.SETTINGS.show_also_hidden_chats = not chat_persistence.SETTINGS.show_also_hidden_chats
        self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())

    def delete_chat(self, conv_id: int):
        """Delete chat."""
        self.root.post_event(APP_EVENTS.DEL_CHAT, int(conv_id))

    def modify_chat(self, conv_id: int, action: Dict):
        """Modify chat."""
        self.root.post_event(APP_EVENTS.MODIFY_CHAT, dict(conv_id=int(conv_id), action=action))

    def new_chat(self):
        """New chat."""
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                None,
                "not used",
                self.root.ai_assistants[self.root.selected_assistant.get()].tokens_used(None),
            ),
        )

    def reload_ai(self):
        """Reload assistants and snippets"""
        self.root.post_event(APP_EVENTS.RELOAD_AI, None)

    def get_chat(self, conv_id: int):
        """
        Callback on chat entry to get and load conversion_id chat

        :param conv_id: conversion_id
        :return:
        """
        self.root.post_event(APP_EVENTS.GET_CHAT, conv_id)
