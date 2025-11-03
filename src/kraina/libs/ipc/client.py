"""App IPC client module.

This module provides a client implementation for inter-process communication
with the krAIna application. It allows external processes to send commands
and receive responses through a socket-based protocol.
"""

import base64
import json
import logging
from typing import Union

from ipyc import IPyCClient

from kraina.libs.ipc.base import APP_KEY
from kraina_chat.base import app_interface

logger = logging.getLogger(__name__)


class AppClient:
    """IPC client for the application.

    This class provides a client interface for communicating with the krAIna
    application through inter-process communication. It handles connection
    management, command validation, and response processing.
    """

    def __init__(self, port=8998):
        """Initialize an IPC client and connect to host.

        Creates a new IPC client instance and establishes a connection to
        the host application on the specified port.

        Args:
            port: Socket port number for the connection (default: 8998)

        """
        self.client = IPyCClient(port=port)
        self._conn = self.client.connect()

    def _send(self, command, params: Union[str, None] = None) -> Union[str, None]:
        """Send the payload with added APP_KEY and wait 30s for ACK.

        Internal method that handles the low-level communication protocol.
        Sends a formatted message with authentication key and waits for
        acknowledgment or response.

        Args:
            command: Command to execute in host
            params: Additional parameters to execute (optional)

        Returns:
            Returned value as string or None if no response received

        """
        to_send = APP_KEY + "|" + command
        if params:
            to_send += "|" + params
        self._conn.send(to_send)
        ret = None
        if self._conn.poll(30.0):
            resp = self._conn.receive()
            if resp:
                resp = resp.split("|")
                if resp[1] not in ["ACK", ""]:
                    ret = str("|".join(resp[1:]))
        return ret

    def send(self, command: str, *args) -> Union[str, None]:
        """Send a message to the host.

        Validates the command against the application interface and sends
        it to the host with any provided arguments.

        Args:
            command: Tk virtual event name which is listed as application Public API
            *args: List of parameters required by command if any

        Returns:
            Returned value as string or None

        Raises:
            AttributeError: If the command is not supported by the application

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

        Closes the connection to the host and cleans up resources.
        """
        self.client.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit method.

        Ensures proper cleanup when exiting a context manager.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        """
        self.stop()

    def __enter__(self):
        """Context manager enter method.

        Returns:
            Self reference for use in context manager

        """
        return self


if __name__ == "__main__":
    c = AppClient()
