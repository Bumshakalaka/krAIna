import sys
import time


def notifier_factory():
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
