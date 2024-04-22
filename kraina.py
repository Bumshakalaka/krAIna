"""Main module."""
import argparse
import logging

from dotenv import load_dotenv, find_dotenv

from libs.MyNotify import NotifyWorking
from skills.base import Skills

load_dotenv(find_dotenv())

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)32s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.ERROR
    logging.basicConfig(format=loggerFormat, level=loggerLevel)

    parser = argparse.ArgumentParser(description="Do various actions with AI")

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

        ret = skills[args.skill].run(args.text)

        desktop_notify.join()
        print(ret)
