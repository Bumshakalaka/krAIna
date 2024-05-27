"""Set of utils functions and classes."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, List


def import_module(path: Path) -> ModuleType:
    """
    Dynamically import a module form path.

    :param path: Path to Python module file
    :return: module
    """
    module_name = path.parent.name
    spec = importlib.util.spec_from_file_location(module_name, str(path), submodule_search_locations=[str(path.parent)])
    sys.modules[module_name] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sys.modules[module_name])
    return sys.modules[module_name]


def str_shortening(data: Any, limit=256) -> str:
    """
    Return a short version of data truncated if data length > limits.

    :param data:
    :param limit:
    :return:
    """
    data = str(data).replace("\n", "\\n")
    if len(data) > limit:
        return (
            data[0 : int(limit / 2)]
            + f"... ({len(data) - (2 * limit)} truncated) ..."
            + data[len(data) - int(limit / 2) :]
        )
    return data


def find_lands(type: str, build_in: Path) -> List[Path]:
    """
    Generate a list of all available assistants/snippets/tools.

    Despite there being built-in types, also search for additional types by searching in root subfolders.
    If the `.kraina-land` label file is inside such a subfolder,
    the folder is a Kraina add-in and is scanned for types.

    :param type: one of the beings as string: assistants, snippets, tools
    :param build_in: Path to build in a set of being type
    :return:
    """
    set_ = [build_in]
    for land in (Path(__file__).parent / "..").glob("*"):
        if not (land.is_dir() or land.name.startswith(".")):
            continue
        enabler = land / ".kraina-land"
        if enabler.exists() and (land / type).exists():
            set_.append(land / type)
    return set_
