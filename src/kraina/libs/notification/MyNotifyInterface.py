"""Abstract base class for notification implementations.

This module defines the interface for notification classes that provide
platform-specific notification functionality. It ensures consistent behavior
across different operating systems.
"""

import abc


class NotifierInterface(abc.ABC):
    """Abstract base class for notification implementations.

    This interface defines the contract for notification classes that provide
    platform-specific notification functionality. It ensures consistent behavior
    across different operating systems.
    """

    @abc.abstractmethod
    def __init__(self, summary: str):
        """Initialize the notification with a summary message.

        :param summary: The main text to display in the notification
        :raises NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    @abc.abstractmethod
    def join(self):
        """Stop and clean up the notification popup.

        This method should properly terminate the notification display
        and clean up any resources used by the notification system.

        :raises NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    @abc.abstractmethod
    def start(self):
        """Start displaying the notification popup.

        This method should begin showing the notification to the user
        and handle any ongoing display logic.

        :raises NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    def __enter__(self):
        """Context manager entry point.

        Starts the notification when entering a context.

        :return: Self instance for context management
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point.

        Stops the notification when exiting a context.

        :param exc_type: Exception type if an exception occurred
        :param exc_val: Exception value if an exception occurred
        :param exc_tb: Exception traceback if an exception occurred
        """
        self.join()
