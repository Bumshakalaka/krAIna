"""Toast popup notification system for krAIna chat application.

This module provides a Toast class that creates temporary popup notifications
positioned at the bottom-right corner of the main application window.
The Toast class implements a singleton pattern where multiple calls append
messages to the same popup and reset the auto-hide timer.
"""

import tkinter as tk
from typing import List, Optional


class Toast(tk.Toplevel):
    """A temporary popup notification widget with singleton behavior.

    The Toast class creates a black popup notification that appears at the
    bottom-right corner of the parent window. Multiple calls to show messages
    will append to the same popup and reset the auto-hide timer.
    """

    _instance: Optional["Toast"] = None
    _messages: List[str] = []
    _after_id: Optional[str] = None
    _configure_binding_id: Optional[str] = None

    def __new__(cls, parent, msg):  # noqa: ARG004
        """Implement singleton pattern for Toast class.

        Args:
            parent: The parent widget (should be the root application window).
            msg: The message to display in the toast.

        Returns:
            Toast: The singleton Toast instance.

        """
        if cls._instance is None or not cls._instance.winfo_exists():
            # Create new instance if none exists or previous was destroyed
            cls._instance = super().__new__(cls)
            cls._messages = []
            cls._after_id = None
            cls._configure_binding_id = None
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, parent, msg):
        """Initialize the Toast popup if not already initialized.

        Args:
            parent: The parent widget (should be the root application window).
            msg: The message to display in the toast.

        """
        if hasattr(self, "_initialized") and self._initialized:
            # Instance already exists, just add message and reset timer
            self._add_message(msg)
            self._reset_timer()
            return

        # Initialize new instance
        super().__init__(parent, bg="black", padx=1, pady=1)
        self.withdraw()  # Hide initially in case there is a delay
        self.overrideredirect(True)

        self.parent = parent
        self._messages = [msg]
        self.message_widget = tk.Message(
            self,
            text="\u26a0 " + msg,
            aspect=1000,
        )
        self.message_widget.grid(padx=2, pady=2)

        # Force update to get proper dimensions
        self.update_idletasks()

        self._update_position()

        # Bind events
        self.bind("<Leave>", self.on_leave)
        self.bind("<Enter>", self.on_enter)

        # Bind configure event on parent.root to reposition toast when main window is resized
        self._configure_binding_id = self.parent.root.bind("<Configure>", self._update_position)

        # Show the toast
        self.deiconify()
        self.lift()  # Bring to front

        # Start auto-hide timer
        self._reset_timer()

        self._initialized = True

    def _add_message(self, msg: str):
        """Add a new message to the existing toast.

        Args:
            msg: The message to add.

        """
        if msg not in self._messages:
            self._messages.append(msg)
            # Update the message widget text
            message_text = "\n".join([f"\u26a0 {m}" for m in self._messages])
            self.message_widget.config(text=message_text)

            # Force update to get proper dimensions and reposition
            self.update_idletasks()
            self._update_position()

    def _reset_timer(self):
        """Reset the auto-hide timer."""
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(5000, self.on_leave)

    def _update_position(self, event=None):  # noqa: ARG002
        """Update the toast position relative to the parent window.

        Repositions the toast at the bottom-right corner of the parent window
        with a 10-pixel padding from the edges.

        Args:
            event: Optional configure event from parent window resize.

        """
        if not self.winfo_exists():
            return
        # Get parent (root) window dimensions and position
        root_width = self.parent.root.winfo_width()
        root_height = self.parent.root.winfo_height()
        root_x = self.parent.root.winfo_x()
        root_y = self.parent.root.winfo_y()

        # Set explicit toast dimensions (Message widget doesn't report dimensions reliably)
        toast_width = self.winfo_reqwidth()
        toast_height = self.winfo_reqheight()

        # Calculate position for right-bottom corner of root window
        # Add some padding (10 pixels) from the edges
        target_x = root_x + root_width - toast_width - 10
        target_y = root_y + root_height - toast_height - 10

        # Set the toast position and size
        self.geometry(f"{toast_width}x{toast_height}+{target_x}+{target_y}")

    def on_leave(self, event=None):  # noqa: ARG002
        """Hide and destroy the toast popup.

        Unbinds the configure event binding and destroys the toast widget.
        This method is called automatically after 2 seconds or when the
        mouse leaves the popup area.

        Args:
            event: Optional leave event from mouse movement.

        """
        # Unbind the configure event before destroying
        if self._configure_binding_id:
            self.parent.root.unbind("<Configure>", self._configure_binding_id)
            self._configure_binding_id = None

        # Reset singleton instance
        Toast._instance = None
        Toast._messages = []
        Toast._after_id = None

        self.destroy()

    def on_enter(self, event=None):  # noqa: ARG002
        """Extend the toast display time when the mouse enters the popup area.

        This method is called when the mouse enters the popup area

        Args:
            event: Optional enter event from mouse movement.

        """
        if self._after_id:
            self.after_cancel(self._after_id)

    @classmethod
    def show(cls, parent, msg):
        """Class method to show a toast message.

        This method provides a cleaner interface for showing toast messages
        and ensures the singleton pattern is properly implemented.

        Args:
            parent: The parent widget (should be the root application window).
            msg: The message to display in the toast.

        Returns:
            Toast: The singleton Toast instance.

        """
        return cls(parent, msg)
