"""Chat with LLM."""
import json
import logging
import queue
import sys
import threading
import tkinter as tk
from collections import defaultdict, namedtuple
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, Union

from dotenv import load_dotenv, find_dotenv
from ttkthemes import ThemedTk

from base import APP_EVENTS, ai_snippets, ai_assistants
from chat_history import ChatFrame
from leftsidebar import LeftSidebar
from status_bar import StatusBar
from menu import Menu

logger = logging.getLogger(__name__)
EVENT = namedtuple("EVENT", "event data")


class App(ThemedTk):
    """Main application."""

    def __init__(self):
        """Create application."""
        super().__init__()
        self._bind_table = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=1)

        self.title("KrAIna CHAT")
        self.set_theme("arc")
        self.selected_assistant = tk.StringVar(self, list(ai_assistants.keys())[0])
        self.protocol("WM_DELETE_WINDOW", self._exito)
        Menu(self)
        pw_main = ttk.PanedWindow(orient=tk.HORIZONTAL)

        left_sidebar = LeftSidebar(self)
        pw_main.add(left_sidebar)

        chat_frame = ChatFrame(self)
        pw_main.add(chat_frame)

        pw_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        StatusBar(self).pack(side=tk.BOTTOM, fill=tk.X)

        self.bind_on_event(APP_EVENTS.QUERY_TO_ASSISTANT, self.call_assistant)
        self.bind_on_event(APP_EVENTS.QUERY_SNIPPET, self.call_snippet)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )
        self._persistent_read()

    def _persistent_write(self):
        """
        Save settings on application exit.

        :return:
        """
        persist_file = Path(__file__).parent / "settings.json"
        data = {"window": {"geometry": self.wm_geometry()}}
        with open(persist_file, "w") as fd:
            json.dump(data, fd)

    def _persistent_read(self):
        """
        Restore settings from persistence if exists.

        :return:
        """
        persist_file = Path(__file__).parent / "settings.json"
        if not persist_file.exists():
            return

        with open(persist_file, "r") as fd:
            data = json.load(fd)

        # Prevent that chat will always be visible
        new_geometry = data["window"]["geometry"]
        w_size, offset_x, offset_y = new_geometry.split("+")
        if (
            int(offset_x) > self.winfo_screenwidth()
            or int(offset_y) > self.winfo_screenheight()
        ):
            new_geometry = "708x437+0+0"
        elif (
            int(w_size.split("x")[0]) > self.winfo_screenwidth()
            or int(w_size.split("x")[1]) > self.winfo_screenheight()
        ):
            new_geometry = "708x437+0+0"
        self.wm_geometry(new_geometry)
        self.update()

    def _exito(self):
        self._persistent_write()
        self.destroy()

    def bind_on_event(self, ev: "APP_EVENTS", cmd: Callable):
        """
        Bind virtual event to callable.

        :param ev: APP_EVENT
        :param cmd: command to execute on event
        :return:
        """
        self._bind_table[ev].append(self._event(cmd))
        self.bind(ev.value, self._event(cmd))

    def post_event(self, ev: "APP_EVENTS", data: Union[str, Dict]):
        """
        Post virtual event with data.

        :param ev: APP_EVENT to post
        :param data: data to pass to bind callable
        :return:
        """
        if len(self._bind_table[ev]) == 0:
            logger.error(f"{ev} not bind")
            return
        self._event_queue.put(EVENT(ev, data))
        self.event_generate(ev.value, when="tail")
        logger.info(f"Post event={ev.name} with data='{data}'")

    def _event(self, ev_cmd):
        def wrapper(event):
            """Decorate bind callable."""
            _data: EVENT = self._event_queue.get()

            ret = ev_cmd(_data.data)
            logger.info(f"React on={_data.event.name} with data='{_data.data}': {ret=}")
            return ret

        return wrapper

    def call_assistant(self, data: Dict):
        """
        Call AI assistant in separate thread.

        Post APP_EVENTS.RESP_FROM_ASSISTANT event when response is ready.

        :param data: Query to be answered by assistant
        :return:
        """
        _call = lambda assistant, query, hist: self.post_event(
            APP_EVENTS.RESP_FROM_ASSISTANT,
            dict(hist=None, query=ai_assistants[assistant].run(query, hist)),
        )
        threading.Thread(
            target=_call,
            args=(self.selected_assistant.get(), data["query"], data["hist"]),
            daemon=True,
        ).start()

    def call_snippet(self, data: Dict):
        """
        Call AI snippet in separate thread to transform data

        Post APP_EVENTS.RESP_FROM_SNIPPET event when response is ready.

        :param data: Dict(entity=snippet name, query=data to transform)
        :return:
        """
        _call = lambda skill, query: self.post_event(
            APP_EVENTS.RESP_FROM_SNIPPET, ai_snippets[skill].run(query)
        )
        threading.Thread(
            target=_call,
            args=(data["entity"], data["query"]),
            daemon=True,
        ).start()


if __name__ == "__main__":
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler("chat.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(
        format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler]
    )
    console_handler.setLevel(logging.INFO)
    load_dotenv(find_dotenv())
    app = App()
    app.mainloop()
