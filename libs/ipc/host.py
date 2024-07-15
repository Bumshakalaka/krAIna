"""App IPC host module."""
import queue
import threading
import logging

from ipyc import IPyCHost

from chat.base import APP_EVENTS, app_interface, ipc_event
from libs.ipc.base import APP_KEY

logger = logging.getLogger(__name__)


def handle_thread_exception(args):
    """Log unexpected exception in the slave threads."""
    logger.exception(
        f"Uncaught exception occurred in thread: {args.thread}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


threading.excepthook = handle_thread_exception


class AppHost(threading.Thread):
    """IPC host threaded for the application."""

    def __init__(self, app):
        """
        Initialise a host on 8998 socket port.

        :param app: Tk main application. It is required to post virtual events
        """
        super().__init__()
        self._host = IPyCHost(port=8998)
        self._app = app
        self.daemon = True

    def run(self):
        """
        Start to listen for the clients.

        When the payload is received, handle it and if successful, send back an ACK.

        :return:
        """
        while True:
            logger.debug(f"waiting for connection")
            client = self._host.wait_for_client()  # blocking
            if client.poll(None):  # blocking
                q = queue.Queue(maxsize=1)
                if self.dispatcher(client.receive(return_on_error=True), q):
                    logger.debug("command posted, waiting for execution")
                    try:
                        # synchronize threads by queue
                        ret = q.get(timeout=30.0)
                    except queue.Empty:
                        ret = "TIMEOUT"
                    client.send(f"{APP_KEY}|{ret if ret is not None else ''}")
                else:
                    # Disconnect client
                    try:
                        client.close()
                    except KeyError as e:
                        # client already disconnected
                        pass

    def dispatcher(self, payload, q: queue.Queue) -> bool:
        """
        Handle received messages.

        :param payload: Received data
        :param q: a response private queue
        :return: Success of not
        """
        if not payload:
            return False
        if len(payload) > 256:
            logger.error("Receive message > 256!")
            return False
        if (message := payload.split("|"))[0] != APP_KEY:
            logger.error("Receive invalid message")
            return False
        if message[1] not in app_interface().keys():
            return False
        self._app.post_event(APP_EVENTS[message[1]], ipc_event(q, None))
        return True
