"""Set of utils functions and classes."""
import importlib.util
import re
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, List, Dict, Tuple

import markdown2


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
def to_md(text: str, col: str = None) -> str:
    """
    Convert markdown text to HTML with optional color styling.

    This function uses markdown2 to convert the input markdown text to HTML. If a color is specified,
    the resulting HTML will be wrapped in a span with the specified color.

    :param text: The markdown text to be converted.
    :param col: Optional. The color to apply to the HTML content.
    :return: The converted HTML string, optionally styled with the specified color.
    """
    html = markdown2.markdown(
        text,
        extras=["tables", "fenced-code-blocks", "cuddled-lists", "code-friendly"],
    )
    return f'<span style="color:{col}">{html}</span>' if col else html


@lru_cache(maxsize=256)
def prepare_message(text: str, tag: str, col: str, sep=True) -> Tuple[str, str]:
    """
    Prepare and format a message based on the given tag and color.

    If the tag is "TOOL", the text is shortened.
    Adds HTML span and horizontal line based on the tag.

    :param text: The input text to be formatted.
    :param tag: The tag indicating the type of message ("HUMAN", "TOOL", etc.).
    :param col: The color to be applied to the text and separators.
    :param sep: Add separators or not.
    :return: The formatted message as a string.
    """
    if sep:
        sep_human = f'\n\n<hr style="height:2px;border-width:0;color:{col};background-color:{col}">\n'
        sep_ai = f'\n\n<hr style="height:4px;border-width:0;color:{col};background-color:{col}">'
    else:
        sep_human = ""
        sep_ai = ""
    text = str_shortening(text) if tag == "TOOL" else text
    if tag == "HUMAN":
        m_text = text.strip() + sep_human
    elif tag == "TOOL":
        m_text = text
    else:
        m_text = text
        if len([index for index in range(len(text)) if text.startswith("```", index)]) % 2 == 1:
            # situation when LLM give text block in ``` but the ``` are unbalanced
            # it can happen when completion tokens where not enough
            m_text += "\n\n```"
        # add horizontal line separator
        m_text += sep_ai
    return m_text, col


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


import inspect


def get_func_args(func) -> Dict:
    """
    Retrieve the argument names and default values of a function.

    This function returns a dictionary where the keys are argument names
    and the values are their default values as strings, or None if no default.

    :param func: The function to inspect.
    :return: A dictionary with argument names and their default values.
    """
    signature = inspect.signature(func)
    ret = {}
    for k, v in signature.parameters.items():
        annot = v.annotation.__name__.replace("_empty", "Any")
        if v.default is not inspect.Parameter.empty:
            ret[f"{k}({annot})"] = str(v.default)
        else:
            ret[f"{k}({annot})"] = None
    return ret


def find_hyperlinks(text: str, no_hyper_tag: str = "") -> list:
    """
    Extract and tag hyperlinks and file paths from text.

    This function identifies URLs and file paths in the input text and tags them
    accordingly, separating them from non-hyperlinked text with a specified tag.

    :param text: The input text containing potential hyperlinks and file paths.
    :param no_hyper_tag: Tag to use for non-hyperlinked text sections.
    :return: A list with parts of the text tagged as hyperlinks or non-hyperlinked text.
    """
    # Regular expressions for URL and file paths
    url_regex = re.compile(r"(https?://[^\s)\",'`]+)")
    posix_path_regex = re.compile(r"(/[^)\s]+\.[^)\s\",'`]+)")
    windows_path_regex = re.compile(r"([a-zA-Z]:\\[^)\",'`\s]+)")

    # Combine all regex patterns
    combined_regex = re.compile(f"{url_regex.pattern}|{posix_path_regex.pattern}|{windows_path_regex.pattern}")

    # Find all matches in the text
    matches = combined_regex.finditer(text)

    parts = []
    last_index = 0

    for match in matches:
        match_str = match.group(0)
        start_index = match.start()

        if last_index < start_index:
            parts.append(text[last_index:start_index])
            parts.append(no_hyper_tag)  # Add empty tag for no hyper text

        parts.append(match_str)
        parts.append(["hyper", no_hyper_tag])

        last_index = match.end()

    if last_index < len(text):
        parts.append(text[last_index:])
        parts.append(no_hyper_tag)  # Add empty tag for no hyper text

    return parts
