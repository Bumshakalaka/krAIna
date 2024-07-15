"""App IPC client module."""
import logging
from typing import Union

from ipyc import IPyCClient

from chat.base import app_interface
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

    def _send(self, payload) -> Union[str, None]:
        """
        Send the payload with added APP_KEY and wait 2s for ACK.

        :param payload:
        :return: returned value as string or None
        """
        self._conn.send(APP_KEY + "|" + payload)
        ret = None
        if self._conn.poll(30.0):
            resp = self._conn.receive().split("|")
            if resp[-1] not in ["ACK", ""]:
                ret = str(resp[-1])
        return ret

    def send(self, message: str) -> Union[str, None]:
        """
        Send a message to the host.

        :param message: Tk virtual event name which is listed as application Public API
        :return: returned value as string or None
        """
        if message not in app_interface().keys():
            logger.error(f"'{message}' not supported")
            return
        return self._send(message)

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
