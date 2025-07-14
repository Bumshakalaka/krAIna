import logging

from kraina.libs.ipc.client import AppClient

logger = logging.getLogger(__name__)


class ChatInterface:
    """Interface for interacting with the KrAIna chat application.

    This class allows sending commands to the chat application and handles connection issues.

    :param silent: If True, suppresses runtime errors when the chat application is not running.
    """

    def __init__(self, silent=False):
        # TODO: Add autorun flag
        self.silent = silent

    def __call__(self, cmd: str, *args, **kwargs):
        """Send a command to the KrAIna chat application.

        Opens a connection to the chat application and sends the specified command.

        :param cmd: The command to be sent to the chat application.
        :param args: Additional positional arguments for the command.
        :param kwargs: Additional keyword arguments for the command.
        :return: The response from the chat application.
        :raises RuntimeError: If the chat application is not running and silent is False.
                AttributeError: If command is not supported
        """
        try:
            with AppClient() as client:
                return client.send(cmd, *args)
        except ConnectionRefusedError:
            if not self.silent:
                raise RuntimeError("KrAIna chat application is not running, start it first") from None


if __name__ == "__main__":
    a = ChatInterface()
    print(a("RUN_SNIPPET", "translate", "co słychać"))
