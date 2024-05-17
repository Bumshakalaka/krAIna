"""App IPC client module."""
import logging

from ipyc import IPyCClient

from chat.base import api_public
from libs.ipc.base import APP_KEY

logger = logging.getLogger(__name__)


class AppClient:
    """IPC client for the application."""

    def __init__(self, port=8998):
        """
        Initialize a IPC client and connect to host.

        :param port: Socket Port
        """
        self.client = IPyCClient(port=port)
        self._conn = self.client.connect()

    def _send(self, payload):
        """
        Send the payload with added APP_KEY and wait 2s for ACK.

        :param payload:
        :return:
        """
        self._conn.send(APP_KEY + "|" + payload)
        if self._conn.poll(2.0):
            self._conn.receive()

    def send(self, message: str):
        """
        Send a message to the host.

        :param message: Tk virtual event name which is listed as application Public API
        :return:
        """
        if message not in api_public():
            logger.error(f"'{message}' not supported")
            return
        self._send(message)

    def stop(self):
        """
        Disconnect from the host.

        :return:
        """
        self.client.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __enter__(self):
        return self


if __name__ == "__main__":
    c = AppClient()
