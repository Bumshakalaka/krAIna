"""Chat with LLM."""
import json
import logging
import queue
import threading
import tkinter as tk
from collections import defaultdict, namedtuple
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, Union, Iterable

from chat.chat_history import ChatFrame
from ttkthemes import ThemedTk

from assistants.assistant import AssistantResp
from chat.base import APP_EVENTS, ai_snippets, ai_assistants
from chat.leftsidebar import LeftSidebar
from chat.menu import Menu
from chat.status_bar import StatusBar
from libs.db.controller import Db
from PIL import ImageTk, Image


logger = logging.getLogger(__name__)
EVENT = namedtuple("EVENT", "event data")


class App(ThemedTk):
    """Main application."""

    def __init__(self):
        """
        Create application.

        IMPORTANT: the application is in withdraw state. `app.deiconify()` method must be called after init
        """
        super().__init__()
        self.withdraw()
        self.ai_db = Db()
        self._bind_table = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=10)
        self.conv_id: Union[int, None] = None
        self.title("KrAIna CHAT")
        self.tk.call(
            "wm", "iconphoto", self._w, ImageTk.PhotoImage(Image.open(str(Path(__file__).parent / "../logo.png")))
        )
        self.set_theme("arc")
        self.selected_assistant = tk.StringVar(self, list(ai_assistants.keys())[0])
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

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
        self.bind_on_event(APP_EVENTS.DEL_CHAT, self.deactivate_chat)
        self.bind_on_event(APP_EVENTS.DESCRIBE_NEW_CHAT, self.describe_chat)
        self.bind_on_event(APP_EVENTS.SHOW_APP, self.show_app)
        self.bind_on_event(APP_EVENTS.HIDE_APP, self.hide_app)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )
        self._persistent_read()
        self.chatW.userW.text.focus_force()

    def show_app(self, *args):
        self.withdraw()
        self.deiconify()
        self.lift()

    def hide_app(self, *args):
        self.wm_state("iconic")

    def describe_chat(self, chat_dump: str):
        """
        Callback on DESCRIBE_NEW_CHAT event to set name and description of the chat.

        :param chat_dump:
        :return:
        """
        if self.ai_db.get_conversation(self.conv_id).name:
            return

        def _call(query):
            try:
                ret = json.loads(ai_snippets["nameit"].run(query))
                self.ai_db.update_conversation(self.conv_id, **ret)
            except Exception as e:
                logger.exception(e)
            self.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, None)

        threading.Thread(
            target=_call,
            args=(chat_dump,),
            daemon=True,
        ).start()

    def deactivate_chat(self, conv_id: int):
        """
        Callback on DEL_CHAT event.

        Deactivate conv_id chat and post ADD_NEW_CHAT_ENTRY event to update chat entries.

        :param conv_id:
        :return:
        """
        self.ai_db.update_conversation(conv_id, active=False)
        self.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, None)

    def update_chat_lists(self, *args):
        """
        Callback in ADD_NEW_CHAT_ENTRY event to get the active conversation list.

        ADD_NEW_CHAT_ENTRY is post without data.
        """
        self.post_event(APP_EVENTS.UPDATE_SAVED_CHATS, self.ai_db.list_conversations(active=True))

    def get_chat(self, conv_id: int):
        """
        Callback on GET_CHAT event.

        :param conv_id: conversation_id from GET_CHAT event
        :return:
        """
        self.conv_id = conv_id
        self.post_event(APP_EVENTS.LOAD_CHAT, self.ai_db.get_conversation(conv_id))

    def _persistent_write(self):
        """
        Save settings on application exit.

        :return:
        """
        persist_file = Path(__file__).parent / "../settings.json"
        data = {"window": {"geometry": self.wm_geometry()}}
        with open(persist_file, "w") as fd:
            json.dump(data, fd)

    def _persistent_read(self):
        """
        Restore settings from persistence if exists.

        :return:
        """
        persist_file = Path(__file__).parent / "../settings.json"
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

    def quit_app(self, *args):
        """Quit application handler."""
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

    def post_event(self, ev: "APP_EVENTS", data: Union[str, Dict, Iterable, None]):
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
        logger.debug(f"Post event={ev.name} with data='{data}'")

    def _event(self, ev_cmd):
        def wrapper(event):
            """Decorate bind callable."""
            _data: EVENT = self._event_queue.get()

            ret = ev_cmd(_data.data)
            logger.debug(f"React on={_data.event.name} with data='{_data.data}': {ret=}")
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
                ret = ai_assistants[assistant].run(query, conv_id=conv_id)
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
