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
from typing import Callable, Dict, Union, Iterable

from dotenv import load_dotenv, find_dotenv
from ttkthemes import ThemedTk

from assistants.assistant import AssistantResp
from base import APP_EVENTS, ai_snippets, ai_assistants
from chat_history import ChatFrame
from leftsidebar import LeftSidebar
from libs.db.controller import Db
from status_bar import StatusBar
from menu import Menu
import pystray
from PIL import Image

logger = logging.getLogger(__name__)
EVENT = namedtuple("EVENT", "event data")


class App(ThemedTk):
    """Main application."""

    def __init__(self):
        """Create application."""
        super().__init__()
        self._bind_table = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=10)
        self.icon = None
        self.conv_id: Union[int, None] = None
        self.title("KrAIna CHAT")
        self.set_theme("arc")
        self.selected_assistant = tk.StringVar(self, list(ai_assistants.keys())[0])
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        Menu(self)
        pw_main = ttk.PanedWindow(orient=tk.HORIZONTAL)

        self.leftsidebarW = LeftSidebar(self)
        pw_main.add(self.leftsidebarW)

        self.chatW = ChatFrame(self)
        pw_main.add(self.chatW)

        pw_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.status = StatusBar(self)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        self.update_chat_lists()

        self.bind_on_event(APP_EVENTS.QUERY_TO_ASSISTANT, self.call_assistant)
        self.bind_on_event(APP_EVENTS.QUERY_SNIPPET, self.call_snippet)
        self.bind_on_event(APP_EVENTS.GET_CHAT, self.get_chat)
        self.bind_on_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, self.update_chat_lists)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )
        self._persistent_read()
        self.chatW.userW.text.focus_force()

    def update_chat_lists(self, *args):
        """
        Callback in ADD_NEW_CHAT_ENTRY event to get the active conversation list.

        ADD_NEW_CHAT_ENTRY is post without data.
        """
        self.post_event(APP_EVENTS.UPDATE_SAVED_CHATS, ai_db.list_conversations(active=True))

    def get_chat(self, conv_id: int):
        """
        Callback on GET_CHAT event.

        :param conv_id: conversation_id from GET_CHAT event
        :return:
        """
        self.conv_id = conv_id
        self.post_event(APP_EVENTS.LOAD_CHAT, ai_db.get_conversation(conv_id))

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
        if int(offset_x) > self.winfo_screenwidth() or int(offset_y) > self.winfo_screenheight():
            new_geometry = "708x437+0+0"
        elif (
            int(w_size.split("x")[0]) > self.winfo_screenwidth()
            or int(w_size.split("x")[1]) > self.winfo_screenheight()
        ):
            new_geometry = "708x437+0+0"
        self.wm_geometry(new_geometry)
        self.update()

    def minimize_to_tray(self):
        """
        React on X (close) press.

        :return:
        """
        self.withdraw()
        image = Image.open(Path(__file__).parent / "krAIna.ico")
        menu = (
            pystray.MenuItem("Show", action=self.show_app, default=True),
            pystray.MenuItem("Quit", self.quit_app, default=False),
        )
        self.icon = pystray.Icon("name", image, "KrAIna chat", menu)
        # threading.Thread(target=lambda: self.icon.run(), daemon=True).start()
        self.icon.run()

    def quit_app(self, *args):
        """Quit application handler."""
        self._persistent_write()
        self.icon.stop()
        self.destroy()

    def show_app(self, *args):
        """Show application handler."""
        self.icon.stop()
        self.after(0, self.deiconify)

    def bind_on_event(self, ev: "APP_EVENTS", cmd: Callable):
        """
        Bind virtual event to callable.

        :param ev: APP_EVENT
        :param cmd: command to execute on event
        :return:
        """
        self._bind_table[ev].append(self._event(cmd))
        self.bind(ev.value, self._event(cmd))

    def post_event(self, ev: "APP_EVENTS", data: Union[str, Dict, Iterable]):
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
        DummyBaseMessage = namedtuple("Dummy", "content response_metadata")

        def _call(assistant, query, conv_id):
            try:
                ret = ai_assistants[assistant].run(query, conv_id)
            except Exception as e:
                logger.exception(e)
                _err = f"FAIL: {type(e).__name__}: {e}"
                ret = AssistantResp(self.conv_id, DummyBaseMessage("", {"token_usage": _err}))
            self.conv_id = ret.conv_id
            self.post_event(APP_EVENTS.RESP_FROM_ASSISTANT, ret.data.content)
            self.status.update_statusbar(ret.data.response_metadata)

        threading.Thread(
            target=_call,
            args=(self.selected_assistant.get(), data, self.conv_id),
            daemon=True,
        ).start()

    def call_snippet(self, data: Dict):
        """
        Call AI snippet in separate thread to transform data

        Post APP_EVENTS.RESP_FROM_SNIPPET event when response is ready.

        :param data: Dict(entity=snippet name, query=data to transform)
        :return:
        """

        def _call(snippet, query):
            try:
                ret = ai_snippets[snippet].run(query)
            except Exception as e:
                ret = str(e)
            self.post_event(APP_EVENTS.RESP_FROM_SNIPPET, ret)

        threading.Thread(
            target=_call,
            args=(data["entity"], data["query"]),
            daemon=True,
        ).start()


if __name__ == "__main__":
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler(Path(__file__).parent / "chat.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler])
    console_handler.setLevel(logging.INFO)
    load_dotenv(find_dotenv())
    ai_db = Db()
    app = App()
    app.mainloop()
