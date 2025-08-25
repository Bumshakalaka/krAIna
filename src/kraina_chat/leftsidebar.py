"""Left sidebar interface for the KrAIna chat application.

This module provides the left sidebar interface containing chat history,
assistant selection, and various management controls for the chat application.
"""

import functools
import logging
import subprocess
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk
from tkinter.simpledialog import Dialog
from typing import Dict, List

from tktooltip import ToolTip

import kraina_chat.chat_persistence as chat_persistence
import kraina_chat.chat_settings as chat_settings
from kraina.assistants.assistant import AssistantResp, AssistantType
from kraina.libs.db.model import Conversations
from kraina_chat.base import APP_EVENTS

logger = logging.getLogger(__name__)


class ChatSettingsDialog(Dialog):
    """Dialog for editing chat conversation settings.

    Provides a modal dialog interface for modifying chat properties
    including name, description, priority, and active status.
    """

    def __init__(self, parent, title, init_values: Conversations):
        """Initialize the chat settings dialog.

        Sets up the dialog with initial values from the provided
        conversation object.

        :param parent: The parent widget
        :param title: The dialog title
        :param init_values: The conversation object containing initial values
        """
        self._e_name = init_values.name
        self._e_description = init_values.description
        self._e_priority = init_values.priority
        self._e_active = init_values.active
        self.conv_id = init_values.conversation_id

        self.e_name: ttk.Entry
        self.e_description: tk.Text
        self.e_priority: ttk.Entry
        self.e_active: tk.BooleanVar
        self.conv_id: int
        super().__init__(parent, title)
        # code here will be run after destroying Dialog

    def buttonbox(self):
        """Override buttonbox to unbind Return key.

        Allows the Return key to be used in text widgets within
        the dialog without closing it.
        """
        super().buttonbox()
        self.unbind("<Return>")

    def body(self, master):
        """Create the dialog body with form fields.

        Builds the form interface with entry fields for name,
        description text area, priority input, and active checkbox.

        :param master: The master widget for the dialog body
        """
        f = ttk.Frame(master)
        ttk.Label(f, text="name", anchor=tk.NW, width=10).pack(side=tk.LEFT)
        w = ttk.Entry(f)
        w.insert(tk.END, self._e_name if self._e_name else "")
        self.e_name = w
        self.e_name.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

        f = ttk.Frame(master)
        ttk.Label(f, text="description", anchor=tk.NW, width=10).pack(side=tk.LEFT)
        w = tk.Text(f, height=10, width=40)
        w.insert(tk.END, self._e_description if self._e_description else "")
        self.e_description = w
        self.e_description.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

        f = ttk.Frame(master)
        ttk.Label(f, text="Priority", anchor=tk.NW, width=10).pack(side=tk.LEFT)
        w = ttk.Entry(f, validate="key", validatecommand=(self.register(self._val_prio), "%P"))
        w.insert(tk.END, str(self._e_priority))
        self.e_priority = w
        self.e_priority.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

        w = tk.BooleanVar(master, value=True)
        w.set(bool(self._e_active))
        self.e_active = w
        f = ttk.Checkbutton(master, text="Active", onvalue=True, offvalue=False, variable=self.e_active)
        f.pack(side=tk.TOP, fill=tk.X, expand=True)

    def _val_prio(self, new_value):
        """Validate priority input field.

        Ensures only numeric values are entered in the priority field.

        :param new_value: The new value being entered
        :return: True if valid, False otherwise
        """
        if new_value == "":
            return True
        try:
            int(new_value)
        except ValueError:
            return False
        else:
            return True

    def apply(self):
        """Apply the dialog changes.

        Collects all form values and posts a MODIFY_CHAT event
        with the updated conversation data.
        """
        action = dict(
            name=self.e_name.get() if self.e_name.get() else None,
            description=self.e_description.get("1.0", tk.END) if self.e_description.get("1.0", tk.END) else None,
            priority=self.e_priority.get() if self.e_priority.get() else 0,
            active=self.e_active.get(),
        )
        self.parent.post_event(APP_EVENTS.MODIFY_CHAT, dict(conv_id=self.conv_id, action=action))  # type: ignore


class LeftSidebar(ttk.Frame):
    """Left sidebar widget for chat management.

    Provides the main navigation and control interface including
    chat history, assistant selection, and various management functions.
    """

    def __init__(self, parent):
        """Initialize the left sidebar.

        Sets up the sidebar layout with chat history, assistant
        selection, and control buttons.

        :param parent: The main application window
        """
        super().__init__(parent)
        self.root = parent
        self.root.bind_on_event(APP_EVENTS.UPDATE_SAVED_CHATS, self.list_saved_chats)
        self.root.bind_on_event(APP_EVENTS.UPDATE_AI, self.list_assistants)
        self.root.bind_on_event(APP_EVENTS.SELECT_CHAT, self.select_chat)
        self.root.bind("<Control-n>", lambda x: self.new_chat())  # noqa: ARG005
        self.root.bind("<Control-N>", lambda x: self.new_chat())  # noqa: ARG005
        # Create Treeview inside Frame
        chats_frame = tk.Frame(self)
        chats_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.chats = ttk.Treeview(chats_frame, columns=("chat_name",), show="headings", selectmode="browse", height=10)

        # Configure the column
        self.chats.heading("chat_name", text="NEW CHAT", command=self.new_chat)  # Hide column header
        self.chats.column("chat_name", anchor="w", stretch=True, width=10)

        self.chats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(chats_frame, orient="vertical", command=self.chats.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chats.configure(yscrollcommand=scrollbar.set)

        # Configure tags for different chat states
        self.chats.tag_configure("pinned", foreground=self.root.get_theme_color("accent"))
        self.chats.tag_configure("inactive", foreground=self.root.get_theme_color("disfg"))
        self.chats.tag_configure("separator", foreground=self.root.get_theme_color("disfg"))

        # Dictionary to store conversation data for each tree item
        self.chat_data = {}

        # Bind events
        self.chats.bind("<<TreeviewSelect>>", self._on_chat_select)
        self.chats.bind("<Button-3>", self._on_chat_context_menu)
        self.chats.bind("<Return>", self._on_enter_key)
        self.chats.bind("<Delete>", self._on_delete_key)

        self.assistants = ttk.LabelFrame(self, text="Assistants", labelanchor="n")
        self.list_assistants()
        self.assistants.pack(side=tk.BOTTOM, fill=tk.X)
        but = ttk.Button(self.assistants, text="RELOAD", command=self.reload_ai)
        self.root.bind("<Control-r>", lambda x: self.reload_ai())  # noqa: ARG005
        self.root.bind("<Control-r>", lambda x: self.reload_ai())  # noqa: ARG005
        ToolTip(but, msg="<CTRL-R> Reload Assistants and Snippets", follow=False, delay=0.5)
        but.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)

    def list_assistants(self, *args):  # noqa: ARG002
        """Populate the assistant list and bind control keys.

        Dynamically creates radio buttons for each assistant, binds
        control key shortcuts, and sets up tooltips and context menus.

        :param args: Additional arguments (not used)
        """
        key = 1
        for n in list(self.assistants.children.keys()):
            if not isinstance(self.assistants.children[n], ttk.Button):
                self.assistants.children[n].destroy()
                self.root.unbind_all(f"<Control-Key-{key}>")
                key += 1
        key = 1
        for name, assistant in self.root.ai_assistants.items():
            name_ = name if assistant.type == AssistantType.SIMPLE else f"{name}(tools)"
            rbut = ttk.Radiobutton(
                self.assistants,
                text=name_,
                variable=self.root.selected_assistant,
                value=name,
                command=self.assistant_change,
            )
            msg_ = f"<CTRL-{key}> "
            msg_ += assistant.description if assistant.description else name_
            if assistant.type == AssistantType.WITH_TOOLS:
                tools_ = "\n- " + "\n- ".join(assistant.tools)
                msg_ += f"\nTools:{tools_}"
            ToolTip(rbut, msg=msg_, follow=False, delay=0.5)
            rbut.bind("<ButtonRelease-3>", self._assistant_menu)
            self.root.bind(f"<Control-Key-{key}>", functools.partial(self._assistant_rbut_select, rbut))
            key += 1
            rbut.pack(side=tk.TOP, fill=tk.X)

    def _assistant_rbut_select(self, w, *args):  # noqa: ARG002
        """Invoke the provided widget's command.

        Helper method to trigger radio button selection via keyboard shortcuts.

        :param w: The widget to invoke
        :param args: Additional arguments (not used)
        """
        w.invoke()

    def _assistant_menu(self, event: tk.Event):
        """Display a context menu for the assistant.

        Creates and displays a context menu with options to edit
        assistant files for non-builtin assistants.

        :param event: The right-click event object
        """
        name = event.widget.configure("text")[-1].split("(")[0]
        if self.root.ai_assistants[name].__buildin__:
            return
        w = tk.Menu(self, tearoff=False)
        w.bind("<FocusOut>", lambda ev: ev.widget.destroy())

        for f in self.root.ai_assistants[name].path.glob("*"):
            if not f.is_dir():
                w.add_command(label=f"{f.name}", command=functools.partial(self.edit_assistant, f))
        try:
            w.tk_popup(event.x_root, event.y_root)
        finally:
            w.grab_release()

    def edit_assistant(self, fn: Path):
        """Open assistant files for editing.

        Opens the specified assistant file using the configured editor
        or falls back to the default web browser.

        :param fn: The file path to open
        """
        if chat_settings.SETTINGS.editor:
            if isinstance(chat_settings.SETTINGS.editor, str):
                args = [chat_settings.SETTINGS.editor]
            else:
                args = chat_settings.SETTINGS.editor
            subprocess.Popen(args + [str(fn)], start_new_session=True)
        else:
            webbrowser.open(str(fn), new=2, autoraise=True)

    def assistant_change(self, *args):  # noqa: ARG002
        """Handle assistant selection change.

        Updates the last assistant setting and posts events to update
        the status bar with token information and API type.

        :param args: Additional arguments (not used)
        """
        chat_persistence.SETTINGS.last_assistant = self.root.selected_assistant.get()
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                self.root.conv_id,
                "not used",
                self.root.current_assistant.tokens_used(self.root.conv_id),
            ),
        )
        self.root.post_event(APP_EVENTS.UPDATE_STATUS_BAR_API_TYPE, chat_persistence.SETTINGS.last_api_type)

    def list_saved_chats(self, conversations: List[Conversations]):
        """Update the saved chats list using Treeview.

        Populates the chat history list with conversation items,
        organizing them by priority and handling active/inactive states.

        :param conversations: List of conversation objects to display
        """
        self.chats.yview_moveto(0.0)  # scroll to the top

        # Clear existing items
        self.chats.delete(*self.chats.get_children())
        self.chat_data.clear()  # Clear conversation data mapping

        separator_added = False

        for conversation in conversations:
            # Handle current chat highlighting
            if conversation.conversation_id == self.root.conv_id:
                self.root.post_event(APP_EVENTS.UPDATE_CHAT_TITLE, conversation)

            # Add separator between pinned and regular chats
            if not separator_added and conversation.priority == 0:
                separator_added = True
                sep_item = self.chats.insert("", "end", values=("─" * 30,), tags=["separator"])
                self.chat_data[sep_item] = None  # No data for separator

            # Create chat item
            name = conversation.name if conversation.name else f"ID:{conversation.conversation_id}"

            # Determine tags
            tags = []
            if conversation.priority > 0:
                tags.append("pinned")
            if not conversation.active:
                tags.append("inactive")
            if conversation.conversation_id == self.root.conv_id:
                tags.append("current")

            # Insert item
            item_id = self.chats.insert("", "end", values=(name,), tags=tags)

            # Store conversation data
            self.chat_data[item_id] = conversation

    def _on_chat_select(self, event):  # noqa: ARG002
        """Handle treeview selection.

        Processes the selection event and loads the selected chat
        conversation.

        :param event: The treeview selection event
        """
        selection = self.chats.selection()
        if not selection:
            return

        item_id = selection[0]
        conversation = self.chat_data.get(item_id)

        # Skip if separator item
        if conversation is None:
            return

        # Load chat
        self.get_chat(conversation.conversation_id)

    def _on_chat_context_menu(self, event):
        """Handle right-click context menu.

        Creates and displays a context menu with options for the
        right-clicked chat conversation.

        :param event: The right-click event object
        """
        # Identify clicked item
        item = self.chats.identify_row(event.y)
        if not item:
            return

        # Select the item
        self.chats.selection_set(item)

        # Get conversation data
        conversation = self.chat_data.get(item)
        if conversation is None:  # Separator item
            return

        # Show context menu
        w = tk.Menu(self, tearoff=False)
        w.bind("<FocusOut>", lambda ev: ev.widget.destroy())

        conv_id = conversation.conversation_id
        pinned = conversation.priority
        active = conversation.active

        w.add_command(label=f"Chat: {conv_id}", state="disabled")
        w.add_command(label="Copy", command=functools.partial(self.copy_chat, conv_id))
        w.add_command(label="Export...", command=functools.partial(self.export_chat, conv_id))
        w.add_command(
            label=f"{'Pin' if pinned == 0 else 'Unpin'}",
            command=functools.partial(self.pin_unpin_chat_tv, conversation),
        )
        w.add_command(
            label=f"{'Inactive' if active else 'Active'}",
            command=functools.partial(self.modify_chat, conv_id, {"active": not active}),
        )
        w.add_command(label="Edit...", command=functools.partial(self.edit_chat_tv, conversation))
        w.add_separator()
        w.add_command(label="Delete", command=functools.partial(self.delete_chat, conv_id))
        w.add_separator()
        w.add_command(
            label=f"{'Hide' if chat_persistence.SETTINGS.show_also_hidden_chats else 'Show'} inactive chats",
            command=self.visibility_chats,
        )

        try:
            w.tk_popup(event.x_root, event.y_root)
        finally:
            w.grab_release()

    def _on_enter_key(self, event):  # noqa: ARG002
        """Handle Enter key - load selected chat.

        Processes the Enter key press to load the currently
        selected chat conversation.

        :param event: The key press event
        """
        selection = self.chats.selection()
        if selection:
            self._on_chat_select(event)

    def _on_delete_key(self, event):  # noqa: ARG002
        """Handle Delete key - delete selected chat.

        Processes the Delete key press to remove the currently
        selected chat conversation.

        :param event: The key press event
        """
        selection = self.chats.selection()
        if selection:
            conversation = self.chat_data.get(selection[0])
            if conversation:
                self.delete_chat(conversation.conversation_id)

    def pin_unpin_chat_tv(self, conversation: Conversations):
        """Pin or unpin chat conversation (Treeview version).

        Toggles the priority of a chat conversation between
        pinned (priority=1) and unpinned (priority=0).

        :param conversation: The conversation object to pin/unpin
        """
        priority = 1 if conversation.priority == 0 else 0
        self.root.post_event(
            APP_EVENTS.MODIFY_CHAT, dict(conv_id=conversation.conversation_id, action={"priority": priority})
        )

    def edit_chat_tv(self, conversation: Conversations):
        """Open chat settings dialog (Treeview version).

        Launches the chat settings dialog for editing the
        specified conversation properties.

        :param conversation: The conversation object to edit
        """
        ChatSettingsDialog(self.root, f"{conversation.conversation_id} Settings", conversation)

    # Old button-based methods removed - replaced with Treeview versions above

    def visibility_chats(self):
        """Toggle visibility of inactive chats.

        Switches between showing all chats or only active chats
        and updates the chat list accordingly.
        """
        chat_persistence.SETTINGS.show_also_hidden_chats = not chat_persistence.SETTINGS.show_also_hidden_chats
        self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())

    def delete_chat(self, conv_id: int):
        """Delete a chat conversation.

        Posts a delete event for the specified conversation.

        :param conv_id: The conversation ID to delete
        """
        self.root.post_event(APP_EVENTS.DEL_CHAT, int(conv_id))

    def modify_chat(self, conv_id: int, action: Dict):
        """Modify chat conversation properties.

        Posts a modify event with the specified changes for the conversation.

        :param conv_id: The conversation ID to modify
        :param action: Dictionary containing the modifications to apply
        """
        self.root.post_event(APP_EVENTS.MODIFY_CHAT, dict(conv_id=int(conv_id), action=action))

    def new_chat(self):
        """Create a new chat session.

        Posts events to start a new chat, update token status,
        and focus the user input area.
        """
        self.root.post_event(APP_EVENTS.NEW_CHAT, None)
        self.root.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                None,
                "not used",
                self.root.current_assistant.tokens_used(None),
            ),
        )
        self.root.chatW.userW.text.focus_force()

    def reload_ai(self):
        """Reload assistants, snippets and saved chats.

        Posts events to reload AI components and refresh the
        chat history list.
        """
        self.root.post_event(APP_EVENTS.RELOAD_AI, None)
        self.root.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())

    def select_chat(self, data: Dict):
        """Select and show a chat conversation.

        Callback for the SELECT_CHAT event that loads the specified chat.

        :param data: Dictionary containing the conversation ID in 'par0'
        """
        self.get_chat(data["par0"])

    def get_chat(self, conv_id: int):
        """Load a chat conversation by ID.

        Posts a GET_CHAT event to retrieve and load the specified
        conversation.

        :param conv_id: The conversation ID to load
        """
        self.root.post_event(APP_EVENTS.GET_CHAT, dict(conv_id=conv_id, ev="LOAD_CHAT"))

    def copy_chat(self, conv_id: int):
        """Copy a chat conversation to clipboard.

        Posts a GET_CHAT event to retrieve and copy the specified
        conversation to the clipboard.

        :param conv_id: The conversation ID to copy
        """
        self.root.post_event(APP_EVENTS.GET_CHAT, dict(conv_id=conv_id, ev="COPY_TO_CLIPBOARD_CHAT"))

    def export_chat(self, conv_id: int):
        """Export a chat conversation to file.

        Posts a GET_CHAT event to retrieve and export the specified
        conversation to a file.

        :param conv_id: The conversation ID to export
        """
        self.root.post_event(APP_EVENTS.GET_CHAT, dict(conv_id=conv_id, ev="EXPORT_CHAT"))
