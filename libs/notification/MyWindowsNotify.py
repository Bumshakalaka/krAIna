import time
from pathlib import Path

from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastProgressBar,
    ToastDisplayImage,
    ToastImagePosition,
)

from libs.notification.MyNotifyInterface import NotifierInterface


class WindowsNotify(NotifierInterface):
    def __init__(self, summary: str):
        self.toaster = InteractableWindowsToaster("kraina", notifierAUMID=r"Microsoft.Windows.Computer")

        toastImage = ToastDisplayImage.fromPath(
            (Path(__file__).parent / "../../img/logo.png").resolve(), position=ToastImagePosition.AppLogo
        )

        progressBar = ToastProgressBar("Working...", progress=None, progress_override="")
        self.newToast = Toast(["KrAIna", summary], progress_bar=progressBar)
        self.newToast.on_dismissed = lambda _: self.toaster.remove_toast(self.newToast)
        self.newToast.AddImage(toastImage)

    def start(self):
        self.toaster.show_toast(self.newToast)

    def join(self):
        self.toaster.remove_toast(self.newToast)


if __name__ == "__main__":
    working = WindowsNotify("AAA")
    working.start()
    time.sleep(4)
    working.join()
