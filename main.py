import argparse
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv, find_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from libs.MyNotify import NotifyWorking
from libs.fernet import Cipher

load_dotenv(find_dotenv())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Do various actions with AI")

    prompts = yaml.safe_load(
        Cipher(os.getenv("DECRYPT_KEY")).file(fn=Path(__file__).parent / "prompts.db")
    )

    parser.add_argument(
        "--action",
        type=str,
        required=True,
        choices=prompts.keys(),
        help="Action to perform",
    )
    parser.add_argument("--text", type=str, required=True, help="User input text")
    args = parser.parse_args()

    action = prompts[args.action]

    destop_notify = NotifyWorking(f"ai:{args.action}")
    destop_notify.start()

    about_me = "  - no information, threat me as average person"
    if args.action == "response":
        if (Path(__file__).parent / "about_me.txt").exists():
            with open(Path(__file__).parent / "about_me.txt") as fd:
                about_me = fd.read()

    chat = ChatOpenAI(**{k: v for k, v in action.items() if k != "prompt"})

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", action["prompt"]),
            ("human", "{text}"),
        ]
    )
    ret = chat.invoke(prompt.format_prompt(text=args.text, about_me=about_me))
    destop_notify.join()
    print(ret.content)
