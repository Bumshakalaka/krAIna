"""Linux notification implementation using GObject introspection.

This module provides a Linux-specific notification implementation that uses
the GObject introspection library to display desktop notifications with
animated progress indicators.
"""

import logging
import threading
import time
from collections import namedtuple

from kraina.libs.notification.MyNotifyInterface import NotifierInterface

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify  # type: ignore # noqa
    NOTIFY_AVAILABLE = True
except (ImportError, ValueError, Exception) as e:
    logger.warning(f"Failed to import Notify library: {e}")
    NOTIFY_AVAILABLE = False
    Notify = None


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
        self._event = threading.Event()
        self._notify_initialized = False

        if not NOTIFY_AVAILABLE:
            logger.warning("Notify library not available, notifications will be disabled")
            return

        try:
            if Notify and Notify.init(summary):
                self._notify_initialized = True
                logger.debug(f"Notify initialized successfully for: {summary}")
            else:
                logger.error("Failed to initialize Notify library")
        except (AttributeError, Exception) as e:
            logger.error(f"Error initializing Notify library: {e}")
            self._notify_initialized = False

    def join(self, timeout=None):
        """Stop the notification and wait for the thread to finish.

        Sets the stop event and waits for the notification thread to complete
        its cleanup operations.

        :param timeout: Maximum time to wait for thread completion in seconds
        """
        self._event.set()
        super().join(timeout)

    def run(self):
        """Execute main notification thread.

        Creates and displays the notification with an animated progress bar.
        The animation cycles through the progress bar dots until the stop
        event is set, then shows a completion message and cleans up.
        """
        if not self._notify_initialized or not NOTIFY_AVAILABLE:
            logger.debug("Notifications disabled, running silent mode")
            # Silent mode - just wait for the event to be set
            while not self._event.is_set():
                time.sleep(0.3)
            return

        try:
            if not Notify:
                raise AttributeError("Notify library not available")

            inf = Notify.Notification.new(self._summary, "Init")
            if not inf.show():
                logger.warning("Failed to show initial notification")
                return

            i = 0
            while not self._event.is_set():
                try:
                    idx = i % len(self._bar)
                    self._bar[idx] = self._dot.full
                    inf.update(self._summary, "".join(self._bar))
                    if not inf.show():
                        logger.warning("Failed to update notification")
                    time.sleep(0.3)
                    self._bar[idx] = self._dot.empty
                    i += 1
                except (AttributeError, Exception) as e:
                    logger.error(f"Error updating notification: {e}")
                    # Continue without notifications
                    break

            try:
                inf.update(self._summary, "Done")
                inf.show()
                time.sleep(0.1)
                inf.close()
            except (AttributeError, Exception) as e:
                logger.error(f"Error closing notification: {e}")

        except (AttributeError, Exception) as e:
            logger.error(f"Error creating notification: {e}")
            # Fall back to silent mode
            while not self._event.is_set():
                time.sleep(0.3)


if __name__ == "__main__":
    working = LinuxNotify("AAA")
    working.start()
    time.sleep(4)
    working.join()
