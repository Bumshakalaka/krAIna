"""Linux notification implementation using GObject introspection.

This module provides a Linux-specific notification implementation that uses
the GObject introspection library to display desktop notifications with
animated progress indicators.
"""

import threading
import time
from collections import namedtuple

import gi

from kraina.libs.notification.MyNotifyInterface import NotifierInterface

gi.require_version("Notify", "0.7")
from gi.repository import Notify  # type: ignore # noqa


class LinuxNotify(threading.Thread, NotifierInterface):
    """Linux notification implementation with animated progress indicator.

    This class provides desktop notifications on Linux systems using the
    GObject introspection library. It displays an animated progress bar
    using dot characters and runs in a separate thread to avoid blocking
    the main application.
    """

    def __init__(self, summary: str):
        """Initialize the Linux notification with a summary message.

        Sets up the notification system, creates the progress bar animation
        components, and initializes the threading infrastructure.

        :param summary: The main text to display in the notification
        """
        super().__init__()
        self._dot = namedtuple("dot", ("empty", "full"))("⚫", "⚪")
        self._bar = [self._dot.empty] * 8
        self._summary = summary
        Notify.init(summary)
        self._event = threading.Event()

    def join(self, timeout=None):
        """Stop the notification and wait for the thread to finish.

        Sets the stop event and waits for the notification thread to complete
        its cleanup operations.

        :param timeout: Maximum time to wait for thread completion in seconds
        """
        self._event.set()
        super().join(timeout)

    def run(self):
        """Execute main notification thread .

        Creates and displays the notification with an animated progress bar.
        The animation cycles through the progress bar dots until the stop
        event is set, then shows a completion message and cleans up.
        """
        inf = Notify.Notification.new(self._summary, "Init")
        inf.show()
        i = 0
        while not self._event.is_set():
            idx = i % len(self._bar)
            self._bar[idx] = self._dot.full
            inf.update(self._summary, "".join(self._bar))
            inf.show()
            time.sleep(0.3)
            self._bar[idx] = self._dot.empty
            i += 1
        inf.update(self._summary, "Done")
        inf.show()
        time.sleep(0.1)
        inf.close()


if __name__ == "__main__":
    working = LinuxNotify("AAA")
    working.start()
    time.sleep(4)
    working.join()
