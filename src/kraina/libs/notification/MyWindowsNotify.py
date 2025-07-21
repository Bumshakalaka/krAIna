"""Windows notification implementation using Windows Toasts.

This module provides a Windows-specific notification implementation that uses
the Windows Toasts API to display modern toast notifications with progress
bars and custom images.
"""

import time
from pathlib import Path

from windows_toasts import (  # type: ignore
    InteractableWindowsToaster,
    Toast,
    ToastDisplayImage,
    ToastImagePosition,
    ToastProgressBar,
)

from kraina.libs.notification.MyNotifyInterface import NotifierInterface


class WindowsNotify(NotifierInterface):
    """Windows notification implementation using Windows Toasts API.

    This class provides modern toast notifications on Windows systems using
    the Windows Toasts library. It displays notifications with progress bars,
    custom images, and interactive elements.
    """

    def __init__(self, summary: str):
        """Initialize the Windows notification with a summary message.

        Sets up the Windows Toaster, creates a toast notification with
        progress bar and custom logo image, and configures dismissal handling.

        :param summary: The main text to display in the notification
        """
        self.toaster = InteractableWindowsToaster("kraina")

        toastImage = ToastDisplayImage.fromPath(
            (Path(__file__).parent / "logo.png").resolve(), position=ToastImagePosition.AppLogo
        )

        progressBar = ToastProgressBar("Working...", progress=None, progress_override="")
        self.newToast = Toast(["KrAIna", summary], progress_bar=progressBar)
        self.newToast.on_dismissed = lambda _: self.toaster.remove_toast(self.newToast)
        self.newToast.AddImage(toastImage)

    def start(self):
        """Display the Windows toast notification.

        Shows the configured toast notification to the user with the
        progress bar and custom image.
        """
        self.toaster.show_toast(self.newToast)

    def join(self):
        """Remove and clean up the Windows toast notification.

        Removes the toast notification from the display and cleans up
        any associated resources.
        """
        self.toaster.remove_toast(self.newToast)


if __name__ == "__main__":
    working = WindowsNotify("AAA")
    working.start()
    time.sleep(4)
    working.join()
