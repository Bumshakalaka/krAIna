"""Command-line interface for KrAIna chat application.

This module provides a command-line interface for interacting with the
KrAIna chat application through IPC communication, allowing external
tools and scripts to send commands to the running application.
"""

import logging

from kraina.libs.ipc.client import AppClient

logger = logging.getLogger(__name__)


class ChatInterface:
    """Interface for interacting with the KrAIna chat application.

    This class allows sending commands to the chat application and handles
    connection issues gracefully. It provides a simple interface for
    external tools to communicate with the running chat application.

    :param silent: If True, suppresses runtime errors when the chat application is not running
    """

    def __init__(self, silent=False):
        """Initialize the chat interface.

        Sets up the interface with optional silent mode for error handling.

        :param silent: Whether to suppress connection errors silently
        """
        # TODO: Add autorun flag
        self.silent = silent

    def __call__(self, cmd: str, *args, **kwargs):  # noqa: ARG002
        """Send a command to the KrAIna chat application.

        Opens a connection to the chat application and sends the specified
        command with any additional arguments. Handles connection errors
        based on the silent mode setting.

        :param cmd: The command to be sent to the chat application
        :param args: Additional positional arguments for the command
        :param kwargs: Additional keyword arguments for the command (currently unused)
        :return: The response from the chat application
        :raises RuntimeError: If the chat application is not running and silent is False
        :raises AttributeError: If the command is not supported by the application
        """
        try:
            with AppClient() as client:
                return client.send(cmd, *args)
        except ConnectionRefusedError:
            if not self.silent:
                raise RuntimeError("KrAIna chat application is not running, start it first") from None


if __name__ == "__main__":
    """Example usage of the ChatInterface.

    Demonstrates how to use the ChatInterface to send a snippet command
    to the running KrAIna chat application.
    """
    a = ChatInterface()
    print(a("RUN_SNIPPET", "translate", "co słychać"))
