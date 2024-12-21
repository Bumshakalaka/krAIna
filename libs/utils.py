"""Set of utils functions and classes."""

import hashlib
import importlib.util
import io
import logging
import re
import shutil
import subprocess
import sys
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, List, Dict, Tuple

import markdown2
import requests
import yaml
from PIL import Image, ImageColor

# mermind prints `Warning: IPython is not installed. Mermaidjs magic function is not available.`
# and we don't want to see this
original_stdout = sys.stdout
sys.stdout = None
import mermaid as md
from mermaid.graph import Graph

sys.stdout = original_stdout


import chat.chat_images as chat_images

logger = logging.getLogger(__name__)


IMAGE_DATA_URL_MARKDOWN_RE = re.compile(r"!\[(?P<img_name>img-[^]]+)\]\((?P<img_data>data:image/[^\)]+)\)")
IMAGE_MARKDOWN_RE = re.compile(r"!\[(?P<img_name>[^]]+)]\((?P<img_url>(https|file)://[^\)]+)\)")
MERMAID_RE = re.compile(r"```\s?(?:mermaid|mmd)\n(?P<graph>[\s\S]*?)```")
LATEX_RE = re.compile(
    r"\\\[(?P<latex>.*?)\\\]|\\\((?P<latex2>.*?)\\\)",
    re.DOTALL,  # Enable multiline matching with dot matching newlines
)


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
    data = str(data).replace("\n", "\\n").replace("img-", "IMG-")
    if len(data) > limit:
        return (
            data[0 : int(limit / 2)]
            + f"... ({len(data) - (2 * limit)} truncated) ..."
            + data[len(data) - int(limit / 2) :]
        )
    return data


def replace_latex(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Replace LaTeX expressions in a text with placeholders.

    This function scans the input text for LaTeX expressions and replaces them
    with unique placeholders, storing the original LaTeX expressions in a dictionary.

    :param text: The input string potentially containing LaTeX expressions.
    :return: A tuple containing the modified text with placeholders and a dictionary
             mapping placeholders to original LaTeX expressions.
    """
    # Store original code blocks
    code_map = {}
    counter = 0

    def _replace(m):
        nonlocal counter
        latex = m.group("latex") or m.group("latex2")
        placeholder = f"__\xd7_latex_{counter}__"
        code_map[placeholder] = latex
        counter += 1
        return placeholder

    text = LATEX_RE.sub(_replace, text)

    return text, code_map


def replace_text(text: str, patterns: list[str]) -> Tuple[str, Dict[str, str]]:
    """
    Replace code blocks in a text with placeholders.

    This function searches for code blocks in the input text using the provided patterns,
    replaces them with unique placeholders, and stores the original code blocks in a map.

    :param text: The input text containing code blocks to be replaced.
    :param patterns: A list of regex patterns to identify code blocks.
    :return: A tuple containing the modified text with placeholders and a dictionary
             mapping placeholders to original code blocks.
    """
    # Store original code blocks
    code_map = {}
    counter = 0

    def _replace(m):
        nonlocal counter
        placeholder = f"__\xd7_{counter}__"
        code_map[placeholder] = m.group(0)
        counter += 1
        return placeholder

    for pattern in patterns:
        text = re.sub(pattern, _replace, text)

    return text, code_map


def restore_text(modified_text: str, code_map: Dict[str, str]) -> str:
    """
    Restore original code blocks from placeholders.

    Args:
        modified_text (str): Text with placeholders
        code_map (Dict[str, str]): Mapping of placeholders to original code

    Returns:
        str: Original text with code blocks restored
    """
    restored_text = modified_text

    # Sort placeholders by length (longest first) to avoid partial replacements
    for placeholder in sorted(code_map.keys(), key=len, reverse=True):
        restored_text = restored_text.replace(placeholder, code_map[placeholder])

    return restored_text


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

    def insert_img(m: re.Match) -> str:
        """Convert Markdown image line into HTML. If image don't exists, create it."""
        name = chat_images.chat_images.create_from_url(m.group("img_data"), m.group("img_name"))
        width, height = chat_images.chat_images.pil_image[name]["resized-150"].size
        return f'<img src="{m.group("img_data")}" alt="{m.group("img_name")}" width="{width}" height="{height}"/>'

    def insert_img_wh(m: re.Match) -> str:
        width, height = 256, 256
        return f'<img src="{m.group("img_url")}" alt="{m.group("img_name")}" width="{width}" height="{height}"/>'

    def insert_mermaid(m: re.Match) -> str:
        name = hashlib.md5(m.group("graph")[0:124].encode()).hexdigest()
        if chat_images.chat_images.get(name):
            width, height = chat_images.chat_images.pil_image[name]["resized-600"].size
            return f'<img src="{chat_images.chat_images.get_file_url(name)}" alt="{name}" width="{width}" height="{height}"/>'
        else:
            graph = Graph("first-graph", m.group("graph"))
            temp = md.Mermaid(graph)
            if temp.img_response.status_code == 200:
                name = chat_images.chat_images.create_from_url(temp.img_response.url, name, False)
                width, height = chat_images.chat_images.pil_image[name]["resized-600"].size
                return f'<img src="{chat_images.chat_images.get_file_url(name)}" alt="{name}" width="{width}" height="{height}"/>'
            else:
                return m.group()

    def insert_latex(latex_, idx_, inverted) -> Tuple[str, str]:
        name = hashlib.md5(latex_[0:124].encode()).hexdigest()
        if chat_images.chat_images.get(name) and chat_images.chat_images.get(name) != "broken":
            return f'<img src="{chat_images.chat_images.get_file_url(name, inverted)}" alt="{name}"/>', idx_
        elif chat_images.chat_images.get(name) != "broken":
            ret = latex_to_image(latex_)
            if ret.get("imageUrl"):
                # ImageTk must be False, as ImageTk.PhotoImage is not thread-safely
                name = chat_images.chat_images.create_from_url(ret.get("imageUrl"), name, False)
                return f'<img src="{chat_images.chat_images.get_file_url(name, inverted)}" alt="{name}"/>', idx_
            else:
                # mark the image as broken, so it will not be process next time
                chat_images.chat_images[name] = "broken"
                return latex_, idx_
        else:
            return latex_, idx_

    text_no_code, code_map = replace_text(MERMAID_RE.sub(insert_mermaid, text), [r"```[\s\S]*?```", r"`[^`]+`"])

    text_no_latex, latex_map = replace_latex(text_no_code)
    if latex_map:
        inverted = False if ImageColor.getcolor(col, "L") < 127 else True  # noqa
        with ThreadPoolExecutor() as executor:
            futures = []
            for idx, latex in {k: v for k, v in latex_map.items()}.items():
                futures.append(executor.submit(insert_latex, latex, idx, inverted))
            for future in as_completed(futures):
                try:
                    ret = future.result()
                    latex_map[ret[1]] = ret[0]
                except Exception as e:
                    raise e

    text = restore_text(
        IMAGE_MARKDOWN_RE.sub(
            insert_img_wh,
            IMAGE_DATA_URL_MARKDOWN_RE.sub(insert_img, restore_text(text_no_latex, latex_map)),
        ),
        code_map,
    )

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


def grabclipboard():
    """Fixed xclip hang version of ImageGrab.grabclipboard()"""
    if sys.platform == "darwin":
        fh, filepath = tempfile.mkstemp(".png")
        os.close(fh)
        commands = [
            'set theFile to (open for access POSIX file "' + filepath + '" with write permission)',
            "try",
            "    write (the clipboard as «class PNGf») to theFile",
            "end try",
            "close access theFile",
        ]
        script = ["osascript"]
        for command in commands:
            script += ["-e", command]
        subprocess.call(script)

        im = None
        if os.stat(filepath).st_size != 0:
            im = Image.open(filepath)
            im.load()
        os.unlink(filepath)
        return im
    elif sys.platform == "win32":
        fmt, data = Image.core.grabclipboard_win32()
        if fmt == "file":  # CF_HDROP
            import struct

            o = struct.unpack_from("I", data)[0]
            if data[16] != 0:
                files = data[o:].decode("utf-16le").split("\0")
            else:
                files = data[o:].decode("mbcs").split("\0")
            return files[: files.index("")]
        if isinstance(data, bytes):
            data = io.BytesIO(data)
            if fmt == "png":
                from PIL import PngImagePlugin

                return PngImagePlugin.PngImageFile(data)
            elif fmt == "DIB":
                from PIL import BmpImagePlugin

                return BmpImagePlugin.DibImageFile(data)
        return None
    else:
        if os.getenv("WAYLAND_DISPLAY"):
            session_type = "wayland"
        elif os.getenv("DISPLAY"):
            session_type = "x11"
        else:  # Session type check failed
            session_type = None

        if shutil.which("wl-paste") and session_type in ("wayland", None):
            args = ["wl-paste", "-t", "image"]
        elif shutil.which("xclip") and session_type in ("x11", None):
            args = ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"]
        else:
            msg = "wl-paste or xclip is required for ImageGrab.grabclipboard() on Linux"
            raise NotImplementedError(msg)
        try:
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            stdout, stderr = p.communicate(timeout=0.5)
        except subprocess.TimeoutExpired:
            stderr = b"cannot convert "
        if stderr:
            for silent_error in [
                # wl-paste, when the clipboard is empty
                b"Nothing is copied",
                # Ubuntu/Debian wl-paste, when the clipboard is empty
                b"No selection",
                # Ubuntu/Debian wl-paste, when an image isn't available
                b"No suitable type of content copied",
                # wl-paste or Ubuntu/Debian xclip, when an image isn't available
                b" not available",
                # xclip, when an image isn't available
                b"cannot convert ",
                # xclip, when the clipboard isn't initialized
                b"xclip: Error: There is no owner for the ",
            ]:
                if silent_error in stderr:
                    return None
            msg = f"{args[0]} error"
            if stderr:
                msg += f": {stderr.strip().decode()}"
            raise ChildProcessError(msg)

        data = io.BytesIO(stdout)
        im = Image.open(data)
        im.load()
        return im


def _convert_data_url_to_file_url(m: re.Match) -> str:
    """
    Convert Markdown data URL image into a file image.

    This function extracts image data and name from a regex match object,
    creates an image file from the data, and returns a Markdown image
    reference pointing to the file.

    :param m: A regex match object containing groups 'img_data' and 'img_name'.
    :return: A Markdown image reference pointing to the created file.
    """
    name = chat_images.chat_images.create_from_url(m.group("img_data"), m.group("img_name"), False)
    return f'![{m.group("img_name")}](file://{chat_images.chat_images.get_file(name)})'


def convert_llm_response(msg: str):
    """
    Convert Markdown data URL image found in message into a file image.

    This function extracts image data and name from a regex match object,
    creates an image file from the data, and returns a Markdown image
    reference pointing to the file.

    :param msg: Message which includes Markdown data URL images
    :return: converted message
    """

    def _convert(m):
        name = chat_images.chat_images.create_from_url(m.group("img_data"), m.group("img_name"), False)
        return f'![{m.group("img_name")}](file://{chat_images.chat_images.get_file(name)})'

    return IMAGE_DATA_URL_MARKDOWN_RE.sub(_convert, msg)


def convert_user_query(msg: str):
    def _convert(m):
        name = chat_images.chat_images.create_from_url(m.group("img_url"), "img-" + m.group("img_name"), False)
        return f'![{"img-" + m.group("img_name")}]({chat_images.chat_images.get_file_url(name)})'

    return IMAGE_MARKDOWN_RE.sub(_convert, msg)


def kraina_db(new_db: str = None) -> str:
    """
    Get or set the path to the Kraina database.

    If a new database name is provided, it sets the environment variable "KRAINA_DB"
    to this new name. It then returns the absolute path to the Kraina database file.

    :param new_db: Optional; The new database name to set in the environment variable.
    :return: The absolute path to the Kraina database file.
    """
    if os.environ.get("KRAINA_DB", None) is None:
        db_settings = {}
        if (Path(__file__).parent / "../config.yaml").resolve().exists():
            with open((Path(__file__).parent / "../config.yaml").resolve(), "r") as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
                db_settings = data.get("db", {})
        if db_settings.get("database", None):
            os.environ["KRAINA_DB"] = str((Path(__file__).parent / "../" / db_settings["database"]).resolve())
        else:
            os.environ["KRAINA_DB"] = str((Path(__file__).parent / "../" / "kraina.db").resolve())
    if new_db:
        os.environ["KRAINA_DB"] = str((Path(__file__).parent / "../" / new_db).resolve())
    return os.environ.get("KRAINA_DB")


def latex_to_image(latex_input=None, output_format="PNG", output_scale="100%"):
    """
    Convert LaTeX input to an image in the specified format and scale.

    This function sends a POST request to an API that converts LaTeX code to an image.
    It prepares the LaTeX input, constructs the payload, and handles the response.

    :param latex_input: The LaTeX code to be converted to an image.
    :param output_format: The desired image format (default is "PNG").
    :param output_scale: The desired scale of the output image (default is "100%").
    :return: A dictionary containing the API response or an error message.
    :raises requests.exceptions.RequestException: If the HTTP request fails.
    """
    # endpoint URL
    url = "https://e1kf0882p7.execute-api.us-east-1.amazonaws.com/default/latex2image"
    out = []
    for line in latex_input.split("\n"):
        if not line.strip():
            continue
        out.append(line.strip())
    out = "\n".join(out)
    # Prepare the payload
    payload = {
        "latexInput": f"\\begin{{align*}}\n{out}\n\\end{{align*}}\n",
        "outputFormat": output_format,
        "outputScale": output_scale,
    }

    # Headers
    headers = {"Content-Type": "application/json"}

    try:
        # Make the POST request
        response = requests.post(url, headers=headers, json=payload)

        # Raise an exception for bad status codes
        response.raise_for_status()

        # Return the JSON response
        ret = response.json()

    except requests.exceptions.RequestException as e:
        ret = {"error": f"Request failed: {str(e)}"}
    logger.debug(f"latex_to_image: {ret}")
    return ret
