"""Main module."""
import argparse
import logging
import sys

from dotenv import load_dotenv, find_dotenv

from libs.MyNotify import NotifyWorking
from skills.base import Skills

load_dotenv(find_dotenv())

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler("kraina.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(
        format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler]
    )
    console_handler.setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(description="Perform various operations with AI")

    skills = Skills()
    parser.add_argument(
        "--skill",
        type=str,
        required=False,
        choices=list(skills.keys()) + [""],
        default="",
        help="Action to perform",
    )
    parser.add_argument(
        "--text", type=str, required=False, default="", help="User query"
    )
    args = parser.parse_args()
    if args.text == "" and args.skill == "":
        print(",".join(skills.keys()))
    else:
        desktop_notify = NotifyWorking(f"ai:{args.skill}")
        desktop_notify.start()
        try:
            ret = skills[args.skill].run(args.text)
            print(ret)
        except Exception as e:
            logger.exception(e)
            exit(1)
        finally:
            desktop_notify.join()
