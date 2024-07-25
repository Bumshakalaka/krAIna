"""Set of utils functions and classes."""
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, List

import markdown


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


@lru_cache(maxsize=1024)
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


@lru_cache(maxsize=256)
def to_md(text: str) -> str:
    """
    Convert text (with html tags) to markdown.

    :param text:
    :return:
    """
    return markdown.markdown(
        text,
        extensions=[
            "pymdownx.superfences",
            "markdown.extensions.md_in_html",
            "markdown.extensions.tables",
            "nl2br",
            "sane_lists",
        ],
    )


@lru_cache(maxsize=256)
def prepare_message(text: str, tag: str, col: str) -> str:
    """
    Prepare and format a message based on the given tag and color.

    If the tag is "TOOL", the text is shortened.
    Adds HTML span and horizontal line based on the tag.

    :param text: The input text to be formatted.
    :param tag: The tag indicating the type of message ("HUMAN", "TOOL", etc.).
    :param col: The color to be applied to the text and separators.
    :return: The formatted message as a string.
    """
    text = str_shortening(text) if tag == "TOOL" else text
    m_text = f'<span style="color:{col}">'
    if tag == "HUMAN":
        m_text += text.strip() + f'\n\n<hr style="height:2px;border-width:0;color:{col};background-color:{col}">\n'
    elif tag == "TOOL":
        m_text += text
    else:
        m_text += text
        if len([index for index in range(len(text)) if text.startswith("```", index)]) % 2 == 1:
            # situation when LLM give text block in ``` but the ``` are unbalanced
            # it can happen when completion tokens where not enough
            m_text += "\n```"
        # add horizontal line separator
        m_text += f'\n\n<hr style="height:4px;border-width:0;color:{col};background-color:{col}">'
    m_text += "</span>"
    return m_text

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
