"""Linux notification implementation using DBus interface.

This module provides a Linux-specific notification implementation that uses
the DBus interface to display desktop notifications with animated progress
indicators.
"""

import threading
import time
from collections import namedtuple

import dbus

from kraina.libs.notification.MyNotifyInterface import NotifierInterface


class LinuxNotify(threading.Thread, NotifierInterface):
    """Linux notification implementation with animated progress indicator.

    This class provides desktop notifications on Linux systems using the
    DBus interface. It displays an animated progress bar using dot characters
    and runs in a separate thread to avoid blocking the main application.
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
        self._done_timeout = 0.5
        self._notification_id = 0
        self._event = threading.Event()

    def _send_notification(
        self, summary, body, app_name="KrAIna", icon="dialog-information", timeout=100, replace_id=0
    ):
        """Send a notification using DBus.

        This function sends a notification using the DBus interface.
        It creates a notification object and sends it to the Notifications service.

        :param summary: The summary of the notification
        :param body: The body of the notification
        :param app_name: The name of the application
        :param icon: The icon of the notification
        :param timeout: The timeout of the notification
        :param replace_id: The replace ID of the notification
        :return: The notification ID
        """
        session_bus = dbus.SessionBus()
        notify_object = session_bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
        notify_interface = dbus.Interface(notify_object, "org.freedesktop.Notifications")

        hints = {
            "x-canonical-private-synchronous": dbus.String(""),
            "transient": dbus.Boolean(True),
        }

        # If icon is not provided, set to empty string
        icon = icon or ""

        # Actions is empty
        actions = []

        # Call Notify method
        notification_id = notify_interface.Notify(
            app_name,  # app_name
            replace_id,  # replaces_id
            icon,  # app_icon
            summary,  # summary
            body,  # body
            actions,  # actions
            hints,  # hints
            timeout,  # expire_timeout (ms)
        )
        return notification_id

    def _close_notification(self, notification_id):
        """Close a notification using DBus.

        :param notification_id: The ID of the notification to close
        """
        try:
            session_bus = dbus.SessionBus()
            notify_object = session_bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
            notify_interface = dbus.Interface(notify_object, "org.freedesktop.Notifications")
            notify_interface.CloseNotification(notification_id)
        except Exception:
            # Ignore errors if notification is already closed or daemon doesn't support it
            pass

    def start(self):
        """Start displaying the notification popup.

        This method begins the notification thread which will show
        the animated progress notification to the user.
        """
        super().start()

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
        # Send initial notification
        self._notification_id = self._send_notification(self._summary, "Init")

        i = 0
        while not self._event.is_set():
            idx = i % len(self._bar)
            self._bar[idx] = self._dot.full
            # Update the same notification using replace_id
            self._notification_id = self._send_notification(
                self._summary, "".join(self._bar), replace_id=self._notification_id
            )
            time.sleep(0.3)
            self._bar[idx] = self._dot.empty
            i += 1

        # Send final "Done" notification
        self._notification_id = self._send_notification(self._summary, "Done", replace_id=self._notification_id)
        time.sleep(self._done_timeout)

        # Manually close the notification after configured delay
        self._close_notification(self._notification_id)


if __name__ == "__main__":
    working = LinuxNotify("AAA")
    working.start()
    time.sleep(4)
    working.join()
