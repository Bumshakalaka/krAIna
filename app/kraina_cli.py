"""Main module."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from kraina.libs.notification.MyNotify import notifier_factory
from kraina.snippets.base import Snippets

load_dotenv(find_dotenv())

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.DEBUG
    file_handler = logging.FileHandler("kraina.log", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler])
    console_handler.setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(
        description="Transform text using snippet.\n"
        "To transform long text like source code or some long paragraph on Windows "
        "the best option is --file parameter as passing the text via command line parameter is problematic.\n"
        "File provided to --file parameter must include name of snippet in first line.\n"
        "The rest of file is treat as text to transform."
    )

    snippets = Snippets()
    parser.add_argument(
        "--snippet",
        type=str,
        required=False,
        choices=list(snippets.keys()) + [""],
        default="",
        help="Snippet to use",
    )
    parser.add_argument("--text", type=str, required=False, default="", help="Text to transform")
    parser.add_argument(
        "--file",
        type=str,
        required=False,
        default="",
        help="Read and parse snippet and text from file.\nFile format: snippet\\ntext, snippet must be in first line.\n"
        "Rest file is treat as text.\nUse instead of --snippet + --text to pass complicated text to transform",
    )

    args = parser.parse_args()
    # Custom validation logic
    if args.file:
        if args.snippet or args.text:
            parser.error("--file cannot be used with --snippet or --text")

    if args.text == "" and args.snippet == "" and args.file == "":
        print(",".join(snippets.keys()))
    else:
        desktop_notify = notifier_factory()(f"KrAina: {args.snippet}")
        desktop_notify.start()
        try:
            if args.file:
                if not (p := Path(args.file)).exists():
                    logger.error(f"'{args.file} dos not exist")
                    exit(1)
                with open(p, "r") as fd:
                    data = fd.read().split("\n")
                    snippet = data[0].strip()
                    query = "\n".join(data[1:])
            else:
                snippet = args.snippet
                query = args.text
            ret = snippets[snippet].run(query)
            # workaround for Windows exception: 'charmap' codec can't encode character
            print(ret.encode("utf-8").decode(sys.stdout.encoding, errors="ignore"))
        except Exception as e:
            logger.exception(e)
            exit(1)
        finally:
            desktop_notify.join()
