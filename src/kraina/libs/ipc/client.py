"""App IPC client module."""

import base64
import json
import logging
from typing import Union

from ipyc import IPyCClient

from kraina.libs.ipc.base import APP_KEY
from kraina_chat.base import app_interface

logger = logging.getLogger(__name__)


class AppClient:
    """IPC client for the application."""

    def __init__(self, port=8998):
        """Initialize a IPC client and connect to host.

        :param port: Socket Port
        """
        self.client = IPyCClient(port=port)
        self._conn = self.client.connect()

    def _send(self, command, params: str = None) -> Union[str, None]:
        """Send the payload with added APP_KEY and wait 30s for ACK.

        :param command: command to execute in host
        :params params: additional parameters to execute
        :return: returned value as string or None
        """
        to_send = APP_KEY + "|" + command
        if params:
            to_send += "|" + params
        self._conn.send(to_send)
        ret = None
        if self._conn.poll(30.0):
            resp = self._conn.receive().split("|")
            if resp[-1] not in ["ACK", ""]:
                ret = str(resp[-1])
        return ret

    def send(self, command: str, *args) -> Union[str, None]:
        """Send a message to the host.

        :param command: Tk virtual event name which is listed as application Public API
        :params args: List of parameters required by command if any
        :return: returned value as string or None
        """
        if command not in app_interface().keys():
            descr = "\n"
            for cmd, cmd_descr in app_interface().items():
                descr += f"\t{cmd} - {cmd_descr}\n"
            raise AttributeError(f"'{command}' not supported.\nSupported commands: {descr}")
        params = None
        if args:
            _params = {}
            for idx, param in enumerate(args):
                _params[f"par{idx}"] = param
            params = base64.b64encode(json.dumps(_params).encode("utf-8")).decode("utf-8")
        return self._send(command, params)

    def stop(self):
        """Disconnect from the host.

        :return:
        """
        self.client.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __enter__(self):
        return self


if __name__ == "__main__":
    c = AppClient()
