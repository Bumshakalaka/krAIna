import abc


class NotifierInterface(abc.ABC):
    """Interface for Notifications."""

    @abc.abstractmethod
    def __init__(self, summary: str):
        raise NotImplementedError

    @abc.abstractmethod
    def join(self):
        """Stop notification popup."""
        raise NotImplementedError

    @abc.abstractmethod
    def start(self):
        """Start notification popup."""
        raise NotImplementedError

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.join()
