"""Base class for macros."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

from kraina.libs.utils import find_assets, import_module

logger = logging.getLogger(__name__)


@dataclass
class Macro:
    """Represents a macro with a file path and an associated method.

    This class holds a path to a file and a callable method associated with it.

    :param path: The file path associated with the macro.
    :param method: A callable method associated with the macro.
    """

    path: Path
    method: Callable


class Macros(Dict[str, Macro]):
    """Base macros."""

    def __init__(self):
        """Initialize macros.

        Iterate over all folders inside macros folder and also search in folders with file tag `.kraina-land`.
        macros/
        ├── pokemon_overview.py
        """
        super().__init__()
        macros_sets = find_assets("macros", Path(__name__).parent)

        for macros_set in macros_sets:
            for macro in macros_set.glob("*"):
                if macro == Path(__name__):
                    continue
                if self.get(macro.stem) is not None:
                    logger.error(f"'{macro.stem}` macro already exist")
                    continue
                if macro.is_dir() or macro.stem.startswith("_") or macro.suffix != ".py":
                    logger.debug("This is not macro")
                    continue
                temp = import_module(macro)
                try:
                    self[macro.stem] = Macro(macro, temp.run)
                except AttributeError:
                    logger.error(f"Required function run() not found in `{macro}` file. Not a macro file.")


if __name__ == "__main__":
    s = Macros()
    for k, v in s.items():
        print(k)
        print(v.__doc__)
