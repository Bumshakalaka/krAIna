"""KrAIna chat."""
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

from chat.chat import App

if __name__ == "__main__":
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler(Path(__file__).parent / "chat.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler])
    console_handler.setLevel(logging.INFO)
    load_dotenv(find_dotenv())
    app = App()
    app.mainloop()
