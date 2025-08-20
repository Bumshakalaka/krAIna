"""Scrolled frame widget for tkinter applications.

This module provides a scrollable frame widget that can contain other widgets
and automatically handle scrolling when content exceeds the visible area.
"""

import logging
import platform
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


class ScrollFrame(ttk.LabelFrame):
    """A scrollable frame widget that can contain other widgets.

    This class creates a frame with automatic scrolling capabilities. It uses
    a canvas with a viewport frame to hold child widgets and automatically
    adjusts scroll regions when content changes.

    Attributes:
        canvas: The underlying canvas widget that handles scrolling.
        viewPort: The frame that contains the child widgets.
        vsb: The vertical scrollbar widget.
        canvas_window: The canvas window item that holds the viewport.

    Reference:
        https://gist.github.com/mp035/9f2027c3ef9172264532fcd6262f3b01

    """

    def __init__(self, parent, *args, **kwargs):
        """Initialize the scrollable frame.

        Args:
            parent: The parent widget.
            *args: Additional positional arguments for LabelFrame.
            **kwargs: Additional keyword arguments for LabelFrame.

        """
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, borderwidth=0)
        self.viewPort = ttk.Frame(self.canvas)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window(
            (4, 4),
            window=self.viewPort,
            anchor="nw",
            tags="self.viewPort",
        )

        self.viewPort.bind("<Configure>", self.onFrameConfigure)
        self.canvas.bind("<Configure>", self.onCanvasConfigure)

        self.viewPort.bind("<Enter>", self.onEnter)
        self.viewPort.bind("<Leave>", self.onLeave)

    def onFrameConfigure(self, event):  # noqa: ARG002
        """Reset the scroll region to encompass the inner frame.

        Args:
            event: The configure event that triggered this callback.

        """
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def onCanvasConfigure(self, event):
        """Reset the canvas window to encompass inner frame when required.

        Args:
            event: The configure event that triggered this callback.

        """
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def onMouseWheel(self, event):
        """Handle mouse wheel scrolling events across different platforms.

        Args:
            event: The mouse wheel event that triggered this callback.

        """
        if platform.system() == "Windows":
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif platform.system() == "Darwin":
            self.canvas.yview_scroll(int(-1 * event.delta), "units")
        else:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

    def onEnter(self, event):  # noqa: ARG002
        """Bind wheel events when the cursor enters the control.

        Args:
            event: The enter event that triggered this callback.

        """
        if platform.system() == "Linux":
            self.canvas.bind_all("<Button-4>", self.onMouseWheel)
            self.canvas.bind_all("<Button-5>", self.onMouseWheel)
        else:
            self.canvas.bind_all("<MouseWheel>", self.onMouseWheel)

    def onLeave(self, event):  # noqa: ARG002
        """Unbind wheel events when the cursor leaves the control.

        Args:
            event: The leave event that triggered this callback.

        """
        if platform.system() == "Linux":
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<MouseWheel>")
