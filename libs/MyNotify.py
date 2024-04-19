import threading
import time
from collections import namedtuple

import gi

gi.require_version("Notify", "0.7")
from gi.repository import Notify


class NotifyWorking(threading.Thread):
    def __init__(self, summary: str, bar_len=4):
        super().__init__()
        self._dot = namedtuple("dot", ("empty", "full"))("⚫", "⚪")
        self._bar = [self._dot.empty] * bar_len
        self._summary = summary
        Notify.init(summary)
        self._event = threading.Event()

    def join(self, timeout=None):
        self._event.set()
        super().join(timeout)

    def run(self):
        inf = Notify.Notification.new(self._summary, "Init")
        inf.show()
        time.sleep(0.7)
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
        time.sleep(0.3)
        inf.close()


if __name__ == "__main__":
    working = NotifyWorking("AAA")
    working.start()
    time.sleep(4)
    working.join()
