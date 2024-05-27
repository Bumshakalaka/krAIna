"""Chat with LLM."""
import functools
import json
import logging
import queue
import threading
import tkinter as tk
from collections import defaultdict, namedtuple
from dataclasses import asdict, replace
from json import JSONDecodeError
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, Union, Iterable

import sv_ttk

from assistants.base import Assistants
from chat.chat_history import ChatFrame

from assistants.assistant import AssistantResp, AssistantType
import chat.chat_settings as chat_settings
from chat.base import APP_EVENTS
from chat.leftsidebar import LeftSidebar
from chat.menu import Menu
from chat.status_bar import StatusBar
from libs.db.controller import Db
from PIL import ImageTk, Image

from libs.utils import str_shortening
from snippets.base import Snippets

logger = logging.getLogger(__name__)
EVENT = namedtuple("EVENT", "event data")


class App(tk.Tk):
    """Main application."""

    def __init__(self):
        """
        Create application.

        IMPORTANT: the application is in withdraw state. `app.deiconify()` method must be called after init
        """
        super().__init__()
        self._persistent_read()
        sv_ttk.set_theme(chat_settings.SETTINGS.theme)
        self.withdraw()
        self.ai_db = Db()
        self.ai_assistants = Assistants()
        self.ai_snippets = Snippets()
        self._bind_table = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=10)
        self.conv_id: Union[int, None] = None
        self.title("KrAIna CHAT")
        self.tk.call(
            "wm", "iconphoto", self._w, ImageTk.PhotoImage(Image.open(str(Path(__file__).parent / "../logo.png")))
        )
        self.selected_assistant = tk.StringVar(self, list(self.ai_assistants.keys())[0])
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
        self.bind_on_event(APP_EVENTS.RELOAD_AI, self.reload_ai)
        self.bind_all("<Escape>", self.hide_app)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )
        self._update_geometry()
        if chat_settings.SETTINGS.last_conv_id:
            self.post_event(APP_EVENTS.GET_CHAT, chat_settings.SETTINGS.last_conv_id)
        if chat_settings.SETTINGS.last_assistant:
            self.selected_assistant.set(chat_settings.SETTINGS.last_assistant)
        self.chatW.userW.text.focus_force()

    def reload_ai(self, *args):
        self.ai_assistants = Assistants()
        self.ai_snippets = Snippets()
        self.post_event(APP_EVENTS.UPDATE_AI, None)

    def show_app(self, *args):
        self.withdraw()
        self.deiconify()
        self.lift()
        if chat_settings.SETTINGS.always_on_top:
            self.wm_attributes("-topmost", True)
        self.chatW.userW.text.focus_force()

    def hide_app(self, *args):
        self.iconify()

    def describe_chat(self, chat_dump: str):
        """
        Callback on DESCRIBE_NEW_CHAT event to set name and description of the chat.

        :param chat_dump:
        :return:
        """
        if self.ai_db.get_conversation(self.conv_id).name:
            return

        def _call(query):
            for _ in range(2):
                try:
                    ret = json.loads(self.ai_snippets["nameit"].run(query))
                    self.ai_db.update_conversation(self.conv_id, **ret)
                except (Exception, JSONDecodeError) as e:
                    logger.exception(e)
                    continue
                else:
                    break
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
        if self.ai_db.is_conversation_id_valid(conv_id):
            self.conv_id = conv_id
            self.post_event(APP_EVENTS.LOAD_CHAT, self.ai_db.get_conversation(conv_id))
            chat_settings.SETTINGS.last_conv_id = self.conv_id
        else:
            logger.error("conversation_id not know")
            self.conv_id = None

    def _persistent_write(self):
        """
        Save settings on application exit.

        :return:
        """
        persist_file = Path(__file__).parent / "../settings.json"
        with open(persist_file, "w") as fd:
            json.dump(asdict(chat_settings.SETTINGS), fd)

    def _persistent_read(self):
        """
        Restore settings from persistence if exists.

        :return:
        """
        persist_file = Path(__file__).parent / "../settings.json"
        if not persist_file.exists():
            return

        with open(persist_file, "r") as fd:
            try:
                chat_settings.SETTINGS = replace(
                    chat_settings.SETTINGS,
                    **{k: v for k, v in json.load(fd).items() if k in chat_settings.SETTINGS.keys()},
                )
            except TypeError as e:
                logger.error("Invalid settings.json format")

    def _update_geometry(self):
        # Prevent that chat will always be visible
        w_size, offset_x, offset_y = chat_settings.SETTINGS.geometry.split("+")
        if int(offset_x) > self.winfo_screenwidth() or int(offset_y) > self.winfo_screenheight():
            chat_settings.SETTINGS.geometry = "708x437+0+0"
        elif (
            int(w_size.split("x")[0]) > self.winfo_screenwidth()
            or int(w_size.split("x")[1]) > self.winfo_screenheight()
        ):
            chat_settings.SETTINGS.geometry = "708x437+0+0"
        self.wm_geometry(chat_settings.SETTINGS.geometry)
        self.update()

    def quit_app(self, *args):
        """Quit application handler."""
        chat_settings.SETTINGS.geometry = self.wm_geometry()
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
        logger.info(f"Post event={ev.name} with data='{str_shortening(data)}'")

    def _event(self, ev_cmd):
        def wrapper(event):
            """Decorate bind callable."""
            _data: EVENT = self._event_queue.get()

            ret = ev_cmd(_data.data)
            logger.info(f"React on={_data.event.name} with data='{str_shortening(_data.data)}': {ret=}")
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
                if self.ai_assistants[assistant].type == AssistantType.WITH_TOOLS:
                    # When assistant with tools is called,
                    # we can assign callback for assistant events to visualize
                    # invoking of the tools
                    self.ai_assistants[assistant].callbacks = dict(
                        action=functools.partial(self.post_event, APP_EVENTS.RESP_FROM_TOOL),
                        observation=functools.partial(self.post_event, APP_EVENTS.RESP_FROM_TOOL),
                        output=None,
                    )
                ret = self.ai_assistants[assistant].run(query, conv_id=conv_id)
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
                ret = self.ai_snippets[snippet].run(query)
            except Exception as e:
                ret = str(e)
            self.post_event(APP_EVENTS.RESP_FROM_SNIPPET, ret)

        threading.Thread(
            target=_call,
            args=(data["entity"], data["query"]),
            daemon=True,
        ).start()
