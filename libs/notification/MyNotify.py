import sys
import time


def notifier_factory():
    if sys.platform == "win32":
        from libs.notification.MyWindowsNotify import WindowsNotify

        return WindowsNotify
    else:
        from libs.notification.MyLinuxNotify import LinuxNotify

        return LinuxNotify


if __name__ == "__main__":
    notifier = notifier_factory()
    working = notifier("AAA")
    working.start()
    time.sleep(4)
    working.join()
