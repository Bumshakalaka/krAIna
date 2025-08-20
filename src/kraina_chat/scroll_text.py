"""Scrolled text widget module providing enhanced text widget with scrollbar functionality.

This module implements a ScrolledText class that extends tkinter.Text with
integrated ttk scrollbar support and proper geometry management.
"""

import tkinter as tk
from tkinter import ttk


class ScrolledText(tk.Text):
    """Enhanced text widget with integrated ttk scrollbar.

    A custom text widget that combines tkinter.Text with ttk.Scrollbar
    for better visual integration and proper geometry management.
    """

    def __init__(self, master=None, **kw):
        """Initialize the scrolled text widget.

        Args:
            master: Parent widget for the scrolled text widget.
            **kw: Additional keyword arguments passed to the Text widget.

        """
        self.frame = ttk.Frame(master)
        self.vbar = ttk.Scrollbar(self.frame)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)

        kw.update({"yscrollcommand": self.vbar.set})
        tk.Text.__init__(self, self.frame, **kw)
        self.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar["command"] = self.yview

        # Copy geometry methods of self.frame without overriding Text
        # methods -- hack!
        text_meths = vars(tk.Text).keys()
        methods = vars(tk.Pack).keys() | vars(tk.Grid).keys() | vars(tk.Place).keys()
        methods = methods.difference(text_meths)

        for m in methods:
            if m[0] != "_" and m != "config" and m != "configure":
                setattr(self, m, getattr(self.frame, m))

    def __str__(self):
        """Return string representation of the frame widget.

        Returns:
            String representation of the underlying frame widget.

        """
        return str(self.frame)
