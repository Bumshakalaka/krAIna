"""App IPC host module.

This module provides a host implementation for inter-process communication
in the krAIna application. It runs as a threaded service that listens for
incoming client connections and dispatches commands to the main application.
"""

import base64
import json
import logging
import queue
import threading

from ipyc import IPyCHost

from kraina.libs.ipc.base import APP_KEY
from kraina_chat.base import APP_EVENTS, app_interface, ipc_event

logger = logging.getLogger(__name__)


def handle_thread_exception(args):
    """Log unexpected exception in the slave threads.

    Global exception handler for threads that logs any uncaught exceptions
    that occur in worker threads.

    Args:
        args: Exception arguments containing thread and exception information

    """
    logger.exception(
        f"Uncaught exception occurred in thread: {args.thread}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


threading.excepthook = handle_thread_exception


class AppHost(threading.Thread):
    """IPC host threaded for the application.

    This class implements a threaded host service that listens for incoming
    client connections and handles command dispatching to the main application.
    It runs as a daemon thread and manages the communication protocol.
    """

    def __init__(self, app):
        """Initialize a host on 8998 socket port.

        Creates a new IPC host instance that will listen for client connections
        on port 8998 and handle command dispatching to the main application.

        Args:
            app: Tk main application instance required to post virtual events

        """
        super().__init__()
        self._host = IPyCHost(port=8998)
        self._app = app
        self.daemon = True

    def run(self):
        """Start to listen for the clients.

        Main thread loop that continuously waits for client connections,
        receives commands, and dispatches them to the main application.
        When a payload is received, it is handled and if successful, an ACK
        is sent back to the client.

        The method runs indefinitely until the thread is terminated.
        """
        while True:
            logger.debug("waiting for connection")
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
                    except KeyError:
                        # client already disconnected
                        pass

    def dispatcher(self, payload, q: queue.Queue) -> bool:
        """Handle received messages.

        Processes incoming messages by validating the authentication key,
        checking command validity, and scheduling execution in the main
        application thread.

        Args:
            payload: Received data from client
            q: Response queue for synchronizing thread communication

        Returns:
            True if message was successfully processed, False otherwise

        """
        if not payload:
            return False
        if (message := payload.split("|"))[0] != APP_KEY:
            logger.error("Receive invalid message")
            return False
        if message[1] not in app_interface().keys():
            return False
        params = None
        if len(message) > 2:
            params = json.loads(base64.b64decode(message[2].encode("utf-8")))
        # schedule to execute IPC action when tk event-loop is idle
        self._app.after_idle(self._app.post_event, APP_EVENTS[message[1]], ipc_event(q, params))
        return True
