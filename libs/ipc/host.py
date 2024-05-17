"""App IPC host module."""
import threading
import logging

from ipyc import IPyCHost

from chat.base import APP_EVENTS, api_public
from libs.ipc.base import APP_KEY

logger = logging.getLogger(__name__)


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
                if self.dispatcher(client.receive(return_on_error=True)):
                    client.send(f"{APP_KEY}|ACK")
                else:
                    # Disconnect client
                    try:
                        client.close()
                    except KeyError as e:
                        # client already disconnected
                        pass

    def dispatcher(self, payload) -> bool:
        """
        Handle received messages.

        :param payload: Received data
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
        if message[1] not in api_public():
            return False
        self._app.post_event(APP_EVENTS[message[1]], None)
        return True
