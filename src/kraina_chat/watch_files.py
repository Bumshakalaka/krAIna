"""File watching module for monitoring changes in krAIna configuration files.

This module provides functionality to watch for file changes in specific
directories and trigger callbacks when relevant files are modified.
"""

import logging
import threading
from pathlib import Path

from watchfiles import Change, DefaultFilter, watch

from kraina.libs.paths import APP_DIR

logger = logging.getLogger(__name__)

watch_exit_event = threading.Event()


class ChatFilter(DefaultFilter):
    """Filter for determining which file changes should trigger actions.

    This filter extends the DefaultFilter to only allow specific file types
    and paths that are relevant to the krAIna application.
    """

    allowed_extensions = ".yaml", ".py", ".env", ".md"
    allowed_path_strings = "assistants", "snippets", ".env", "config.yaml", "macros"

    def __call__(self, change: Change, path: str) -> bool:
        """Determine if a file change should trigger an action.

        This method checks if the file change matches the allowed extensions,
        path strings, and is of type 'modified'.

        Args:
            change: The type of change detected (e.g., modified, added).
            path: The file path that has changed.

        Returns:
            True if the change should be processed, False otherwise.

        """
        return (
            super().__call__(change, path)
            and any(True for part in self.allowed_path_strings if part in path)
            and path.endswith(self.allowed_extensions)
            and change == Change.modified
        )


def watch_my_files(callback):
    """Monitor specific file changes and trigger a callback.

    This function watches files in the parent directory for any modifications
    that match the criteria defined in ChatFilter. When a change is detected,
    it logs the change and calls the provided callback with a string indicating
    the type of file changed.

    Args:
        callback: A function to be called when a relevant file change is detected.
                 The callback receives a string argument indicating the type of file.

    """

    def _call(cbk):
        for changes in watch(
            APP_DIR,
            recursive=True,
            step=1000,
            watch_filter=ChatFilter(),
            stop_event=watch_exit_event,
        ):
            for change in changes:
                logger.info(f"Change detected: {change}")
                if not cbk:
                    continue
                if "assistants" in (pp := Path(change[1]).parts):
                    cbk("assistants")
                elif "snippets" in pp:
                    cbk("snippets")
                elif "macros" in pp:
                    cbk("macros")
                elif pp[-1] in [".env", "config.yaml"]:
                    cbk("main")

    threading.Thread(
        target=_call,
        args=(callback,),
        daemon=True,
    ).start()
