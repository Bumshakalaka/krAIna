"""Main module."""
import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

from libs.notification.MyNotify import notifier_factory
from snippets.base import Snippets

load_dotenv(find_dotenv())

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler("kraina.log", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler])
    console_handler.setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(description="Perform various operations with AI")

    snippets = Snippets()
    parser.add_argument(
        "--snippet",
        type=str,
        required=False,
        choices=list(snippets.keys()) + [""],
        default="",
        help="Action to perform",
    )
    parser.add_argument("--text", type=str, required=False, default="", help="User query")
    parser.add_argument("--file", type=str, required=False, default="", help="Read snippet + query from file")

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
                    snippet = data[0]
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
