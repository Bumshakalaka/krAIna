"""Base class for macros."""
import logging
from pathlib import Path
from typing import Dict, Callable

from libs.utils import import_module, find_lands

logger = logging.getLogger(__name__)


class Macros(Dict[str, Callable]):
    """Base macros."""

    def __init__(self):
        """
        Initialize macros.

        Iterate over all folders inside macros folder and also search in folders with file tag `.kraina-land`.
        macros/
        ├── pokemon_overview.py
        """
        super().__init__()
        macros_sets = find_lands("macros", Path(__file__).parent)

        for macros_set in macros_sets:
            for macro in macros_set.glob("*"):
                if macro == Path(__file__):
                    continue
                if self.get(macro.stem) is not None:
                    logger.error(f"'{macro.stem}` macro already exist")
                    continue
                if macro.is_dir() or macro.stem.startswith("_") or macro.suffix != ".py":
                    logger.debug("This is not macro")
                    continue
                temp = import_module(macro)
                try:
                    self[macro.stem] = temp.run
                except AttributeError:
                    logger.error(f"Required function run() not found in `{macro}` file. Not a macro file.")


if __name__ == "__main__":
    s = Macros()
    for k, v in s.items():
        print(k)
        print(v.__doc__)
