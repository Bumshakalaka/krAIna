"""GUI menu."""
import tkinter as ttk


class FileMenu(ttk.Menu):
    """File sub-menu class."""

    def __init__(self, parent, *args, **kwargs):
        """Create menu."""
        super().__init__(parent, *args, **kwargs)
        self.add_command(
            label="Open DB...",
        )
        self.add_command(
            label="Key DB...",
        )
        self.add_separator()
        self.add_command(label="Exit", command=parent.destroy)


class Menu(ttk.Menu):
    """GUI menu."""

    def __init__(self, parent):
        """Create menu."""
        super().__init__(parent)
        parent.config(menu=self)
        self.add_cascade(label="File", menu=FileMenu(parent, tearoff=0))
