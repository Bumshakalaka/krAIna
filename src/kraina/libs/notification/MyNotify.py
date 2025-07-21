"""Notification factory module for platform-specific notification handling.

This module provides a factory function that returns the appropriate notification
class based on the current operating system platform.
"""

import sys
import time


def notifier_factory():
    """Create and return the appropriate notification class for the current platform.

    Determines the operating system and imports the corresponding notification
    implementation. Supports Windows and Linux platforms.

    :return: The notification class appropriate for the current platform
    :raises ImportError: If the platform-specific notification module cannot be imported
    """
    if sys.platform == "win32":
        from kraina.libs.notification.MyWindowsNotify import WindowsNotify

        return WindowsNotify
    else:
        from kraina.libs.notification.MyLinuxNotify import LinuxNotify

        return LinuxNotify


if __name__ == "__main__":
    notifier = notifier_factory()
    working = notifier("AAA")
    working.start()
    time.sleep(4)
    working.join()
