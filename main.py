import argparse
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv, find_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from libs.fernet import Cipher

load_dotenv(find_dotenv())
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Do various actions with AI")

    parser.add_argument("--action", type=str, required=True, help="Action to perform")
    parser.add_argument("--text", type=str, required=True, help="text to translate")
    args = parser.parse_args()

    prompts = yaml.safe_load(Cipher(os.getenv("DECRYPT_KEY")).file(fn=Path(__file__).parent / "prompts.db"))

    system_prompt = prompts[args.action]

    chat = ChatOpenAI(temperature=1, model="gpt-3.5-turbo")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{text}"),
        ]
    )
    ret = chat.invoke(prompt.format_prompt(text=args.text))
    print(ret.content)
