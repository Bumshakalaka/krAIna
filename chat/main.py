"""Chat with LLM."""
import collections
import functools
import json
import logging
import queue
import sys
import threading
import tkinter as tk
from collections import defaultdict, namedtuple
from dataclasses import asdict, replace
from json import JSONDecodeError
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, Union, Any

import klembord
import sv_ttk
import yaml
from PIL.ImageChops import darker

from assistants.base import Assistants
from chat.chat_history import ChatFrame

from assistants.assistant import AssistantResp, AssistantType
import chat.chat_settings as chat_settings
import chat.chat_persistence as chat_persistence
from chat.base import APP_EVENTS, ipc_event, get_windows_version
from chat.leftsidebar import LeftSidebar
from chat.menu import Menu
from chat.status_bar import StatusBar
from libs.db.controller import Db
from PIL import ImageTk, Image

from libs.llm import get_llm_type, SUPPORTED_API_TYPE
from libs.utils import str_shortening, prepare_message, to_md
from snippets.base import Snippets
from snippets.snippet import BaseSnippet

# Configure global logger
loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
loggerFormatter = logging.Formatter(loggerFormat)
loggerLevel = logging.DEBUG
# create stderr logger to have only ERRORs there
console_handler = logging.StreamHandler(sys.stderr)
logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[console_handler])
console_handler.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

EVENT = namedtuple("EVENT", "event data")


def handle_thread_exception(args):
    """Log unexpected exception in the slave threads."""
    logger.exception(
        f"Uncaught exception occurred in thread: {args.thread}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


threading.excepthook = handle_thread_exception


class NotifyErrorFilter(logging.Filter):
    """Execute function on every error log message."""

    def __init__(self, error_cbk: Callable):
        super().__init__()
        self.error_cbk = error_cbk

    def filter(self, record: logging.LogRecord):
        if record.levelno >= 40:
            self.error_cbk()
        return True


class QueueHandler(logging.Handler):
    """Class to send logging records to a queue."""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        """Store log record in queue."""
        self.log_queue.append(record)


class App(tk.Tk):
    """Main application."""

    def __init__(self):
        """
        Create application.

        IMPORTANT: the application is in withdraw state. `app.deiconify()` method must be called after init
        """
        super().__init__()
        self._bind_table = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=20)

        # Configure application queue logger which is required for Debug Window
        self.log_queue = collections.deque(maxlen=1000)
        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.addFilter(
            NotifyErrorFilter(lambda: self.after_idle(self.post_event, APP_EVENTS.WE_HAVE_ERROR, None))
        )
        self.queue_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"))
        self.queue_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self.queue_handler)

        self._settings_read()
        self._persistent_read()
        style = ttk.Style(self)
        sv_ttk.get_theme(self)  # required to load svv themes and have them visible by style
        style.theme_use(chat_persistence.SETTINGS.theme)
        self.set_title_bar_color(chat_persistence.SETTINGS.theme)
        style.configure("Hidden.TButton", foreground=self.get_theme_color("disfg"))
        style.configure("ERROR.TButton", foreground="red")
        self.withdraw()
        self.ai_db = Db()
        self.ai_assistants = Assistants()
        self.ai_snippets: Dict[str, BaseSnippet] = Snippets()
        self.conv_id: Union[int, None] = None
        self.title("KrAIna CHAT")
        self.tk.call(
            "wm",
            "iconphoto",
            self._w,
            ImageTk.PhotoImage(Image.open(str(Path(__file__).parent / "../img/logo_big.png"))),
        )
        self.selected_assistant = tk.StringVar(self, list(self.ai_assistants.keys())[0])
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

        Menu(self)
        self.pw_main = tk.PanedWindow(orient=tk.HORIZONTAL, height=80, opaqueresize=False, sashpad=2, sashwidth=4)

        self.leftsidebarW = LeftSidebar(self)
        self.pw_main.add(self.leftsidebarW)

        self.chatW = ChatFrame(self)
        self.pw_main.add(self.chatW)
        self.pw_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        def _set_sashpos(event):
            # I have no idea how to set sash pos other way.
            # It must be done when the widget is fully updated.
            # Thus, do this one time on Configure event
            self.pw_main.sash_place(0, chat_persistence.SETTINGS.sashpos_main, 1)
            self.pw_main.unbind("<Configure>")

        self.pw_main.bind("<Configure>", _set_sashpos)
        self.status = StatusBar(self)
        self.status.pack(side=tk.BOTTOM, fill=tk.BOTH)
        self.update_chat_lists(active=chat_persistence.show_also_hidden_chats())

        self.bind_on_event(APP_EVENTS.QUERY_TO_ASSISTANT, self.call_assistant)
        self.bind_on_event(APP_EVENTS.QUERY_SNIPPET, self.call_snippet)
        self.bind_on_event(APP_EVENTS.RUN_SNIPPET, self.call_snippet_ipc)
        self.bind_on_event(APP_EVENTS.GET_CHAT, self.get_chat)
        self.bind_on_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, self.update_chat_lists)
        self.bind_on_event(APP_EVENTS.DEL_CHAT, self.delete_chat)
        self.bind_on_event(APP_EVENTS.MODIFY_CHAT, self.modify_chat)
        self.bind_on_event(APP_EVENTS.DESCRIBE_NEW_CHAT, self.describe_chat)
        self.bind_on_event(APP_EVENTS.SHOW_APP, self.show_app)
        self.bind_on_event(APP_EVENTS.HIDE_APP, self.hide_app)
        self.bind_on_event(APP_EVENTS.RELOAD_AI, self.reload_ai)
        self.bind_on_event(APP_EVENTS.GET_LIST_OF_SNIPPETS, lambda x: ",".join(self.ai_snippets.keys()))
        self.bind_on_event(APP_EVENTS.COPY_TO_CLIPBOARD, self.copy_to_clipboard)
        self.bind_on_event(
            APP_EVENTS.RELOAD_CHAT_LIST,
            lambda x: self.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats()),
        )
        self.bind("<Escape>", self.hide_app)
        self.bind_class(
            "Text",
            "<Control-a>",
            lambda event: event.widget.event_generate("<<SelectAll>>"),
        )
        self._update_geometry()
        if chat_persistence.SETTINGS.last_conv_id:
            self.post_event(APP_EVENTS.GET_CHAT, dict(conv_id=chat_persistence.SETTINGS.last_conv_id, ev="LOAD_CHAT"))
        if chat_persistence.SETTINGS.last_assistant:
            self.selected_assistant.set(chat_persistence.SETTINGS.last_assistant)
        self.setvar(
            "selected_api_type",
            "-" if chat_persistence.SETTINGS.last_api_type == "" else chat_persistence.SETTINGS.last_api_type,
        )
        self.chatW.userW.text.focus_force()

    @property
    def current_assistant(self):
        """Get current assistant."""
        try:
            self.ai_assistants[self.selected_assistant.get()]
        except KeyError as e:
            if (
                chat_settings.SETTINGS.default_assistant
                and chat_settings.SETTINGS.default_assistant in self.ai_assistants
            ):
                self.selected_assistant.set(chat_settings.SETTINGS.default_assistant)
            else:
                self.selected_assistant.set(list(self.ai_assistants.keys())[0])

            logger.warning(
                f"{e} assistant does not exist anymore, use '{self.selected_assistant.get()}' one as fallback"
            )
        return self.ai_assistants[self.selected_assistant.get()]

    def copy_to_clipboard(self, text: str):
        """
        Copy Last AI response to system clipboard in Text and HTML format.

        :param text:
        :return:
        """
        if not chat_persistence.SETTINGS.copy_to_clipboard:
            return
        klembord.init()
        if sys.platform == "win32":
            klembord.set(
                {
                    "HTML Format": klembord.wrap_html(
                        to_md(prepare_message(text, "AI", str(self.get_theme_color("fg", "sun-valley-light")), False))
                    ),
                    "CF_UNICODETEXT": text.encode("utf-16le"),
                }
            )
        else:
            klembord.set(
                {
                    "UTF8_STRING": text.encode(),
                    "text/html": to_md(
                        prepare_message(text, "AI", str(self.get_theme_color("fg", "sun-valley-light")), False)
                    ).encode(),
                }
            )

    def set_title_bar_color(self, theme):
        """Set background color of title on Windows only."""
        if get_windows_version() == 10:
            import pywinstyles

            if "dark" in theme:
                pywinstyles.apply_style(self, "dark")
            else:
                pywinstyles.apply_style(self, "normal")

            # A hacky way to update the title bar's color on Windows 10 (it doesn't update instantly like on Windows 11)
            self.wm_attributes("-alpha", 0.99)
            self.wm_attributes("-alpha", 1)
        elif get_windows_version() == 11:
            import pywinstyles

            if "dark" in theme:
                take_from = "dark"
            else:
                take_from = "light"
            col = str(self.tk.call("set", f"ttk::theme::sv_{take_from}::colors(-bg)"))
            # Set the title bar color to the background color on Windows 11 for better appearance
            pywinstyles.change_header_color(self, col)

    def get_theme_color(self, col_name, theme=None) -> str:
        """Get theme color based on actual theme."""
        if not theme:
            theme = ttk.Style(self).theme_use()
        if "dark" in theme:
            take_from = "dark"
        else:
            take_from = "light"
        if "sun-" in theme:
            col = self.tk.call("set", f"ttk::theme::sv_{take_from}::colors(-{col_name})")
        else:
            col_map = {
                "accent": "#005fb8",
                "bg": ttk.Style(self).lookup("", "background"),
                "fg": ttk.Style(self).lookup("", "foreground"),
                "disfg": ttk.Style(self).lookup("", "foreground"),
            }
            col = col_map[col_name]
        return col

    def report_callback_exception(self, exc, val, tb):
        """Handle tkinter callback errors"""
        logger.exception(exc)

    def reload_ai(self, *args):
        self.ai_assistants = Assistants()
        self.ai_snippets = Snippets()
        self.post_event(APP_EVENTS.UPDATE_AI, None)

    def show_app(self, *args):
        self.withdraw()
        self.deiconify()
        # workaround to lift window on Linux and Windows
        # On Windows self.lift() doesn't work always
        self.wm_attributes("-topmost", True)
        if chat_persistence.SETTINGS.always_on_top:
            self.wm_attributes("-topmost", True)
        else:
            self.wm_attributes("-topmost", False)
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
            if get_llm_type(self.ai_snippets["nameit"].force_api) == SUPPORTED_API_TYPE.ANTHROPIC:
                logger.warning("Chat description via Anthropic is not supported")
                return
            # get an assistant API type to avoid using built one in snippet
            # and avoid data disclosure
            temp = self.ai_snippets["nameit"].force_api
            self.ai_snippets["nameit"].force_api = self.current_assistant.force_api
            for _ in range(2):
                try:
                    ret = json.loads(
                        self.ai_snippets["nameit"]
                        .run(query)
                        .removesuffix("```")
                        .removeprefix("```")
                        .removeprefix("json")
                    )
                    self.ai_db.update_conversation(self.conv_id, **ret)
                except (Exception, JSONDecodeError) as e:
                    logger.exception(e)
                    continue
                else:
                    break
            self.ai_snippets["nameit"].force_api = temp
            self.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())

        threading.Thread(
            target=_call,
            args=(chat_dump,),
            daemon=True,
        ).start()

    def delete_chat(self, conv_id: int):
        """
        Callback on DEL_CHAT event.

        Permanent delete conv_id chat and post ADD_NEW_CHAT_ENTRY event to update chat entries.

        :param conv_id:
        :return:
        """
        self.ai_db.delete_conversation(conv_id)
        self.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())
        self.post_event(APP_EVENTS.NEW_CHAT, None)
        self.post_event(
            APP_EVENTS.UPDATE_STATUS_BAR_TOKENS,
            AssistantResp(
                None,
                "not used",
                self.current_assistant.tokens_used(None),
            ),
        )

    def modify_chat(self, data: Dict):
        """
        Callback on MODIFY_CHAT event.

        Modify conv_id chat and post ADD_NEW_CHAT_ENTRY event to update chat entries.

        :param data:
        :return:
        """
        conv_id = data["conv_id"]
        action = data["action"]  # type: Dict
        self.ai_db.update_conversation(conv_id, **action)
        self.post_event(APP_EVENTS.ADD_NEW_CHAT_ENTRY, chat_persistence.show_also_hidden_chats())

    def update_chat_lists(self, active: Union[bool, None]):
        """
        Callback in ADD_NEW_CHAT_ENTRY event to get the conversation list.

        ADD_NEW_CHAT_ENTRY is post without data.

        :param active: Get active(True), inactive(False) or both(None) conversations
        :return:
        """
        self.post_event(
            APP_EVENTS.UPDATE_SAVED_CHATS,
            self.ai_db.list_conversations(active=active, limit=chat_settings.SETTINGS.visible_last_chats),
        )

    def get_chat(self, data: dict):
        """
        Callback on GET_CHAT event.

        :param conv_id: conversation_id from GET_CHAT event
        :return:
        """
        if self.ai_db.is_conversation_id_valid(data["conv_id"]):
            self.conv_id = data["conv_id"]
            self.post_event(APP_EVENTS[data["ev"]], self.ai_db.get_conversation(data["conv_id"]))
            if data["ev"] == "LOAD_CHAT":
                chat_persistence.SETTINGS.last_conv_id = self.conv_id
        else:
            logger.error("conversation_id not know")
            if data["ev"] == "LOAD_CHAT":
                self.conv_id = None

    def _persistent_write(self):
        """
        Save settings on application exit.

        :return:
        """
        persist_file = Path(__file__).parent / "../.settings.yaml"
        chat_persistence.SETTINGS.sashpos_main = list(self.pw_main.sash_coord(0))[0]
        chat_persistence.SETTINGS.sashpos_chat = list(self.chatW.sash_coord(0))[1]
        with open(persist_file, "w") as fd:
            yaml.dump(dict(chat=asdict(chat_persistence.SETTINGS)), fd)

    def _persistent_read(self):
        """
        Restore settings from persistence if exists.

        :return:
        """
        persist_file = Path(__file__).parent / "../.settings.yaml"
        if not persist_file.exists():
            return

        with open(persist_file, "r") as fd:
            try:
                data = yaml.load(fd, Loader=yaml.SafeLoader)["chat"]
                chat_persistence.SETTINGS = replace(
                    chat_persistence.SETTINGS,
                    **{k: v for k, v in data.items() if k in chat_persistence.SETTINGS.keys()},
                )
            except TypeError as e:
                logger.error("Invalid .settings.yaml format")

    def _settings_read(self):
        """
        Get settings from config.yaml file.

        :return:
        """
        settings_file = Path(__file__).parent / "../config.yaml"
        if not settings_file.exists():
            return

        with open(settings_file, "r") as fd:
            try:
                data = yaml.load(fd, Loader=yaml.SafeLoader)["chat"]
                chat_settings.SETTINGS = replace(
                    chat_settings.SETTINGS,
                    **{k: v for k, v in data.items() if k in chat_settings.SETTINGS.keys()},
                )
                # # fill persistence with default values
                # for k in set(chat_persistence.SETTINGS.keys()) & set(chat_settings.SETTINGS.keys()):
                #     setattr(chat_persistence.SETTINGS, k, getattr(chat_settings.SETTINGS, k))
            except TypeError as e:
                logger.error("Invalid config.yaml format")

    def _update_geometry(self):
        if chat_persistence.SETTINGS.geometry == "zoomed":
            self.wm_state("zoomed")
        else:
            # Prevent that chat will always be visible
            w_size, offset_x, offset_y = chat_persistence.SETTINGS.geometry.split("+")
            if int(offset_x) > self.winfo_screenwidth() or int(offset_y) > self.winfo_screenheight():
                chat_persistence.SETTINGS.geometry = "708x546+0+0"
            elif (
                int(w_size.split("x")[0]) > self.winfo_screenwidth()
                or int(w_size.split("x")[1]) > self.winfo_screenheight()
            ):
                chat_persistence.SETTINGS.geometry = "708x546+0+0"
            self.wm_geometry(chat_persistence.SETTINGS.geometry)
        self.update()

    def quit_app(self, *args):
        """Quit application handler."""
        if self.wm_state() == "zoomed":
            chat_persistence.SETTINGS.geometry = "zoomed"
        else:
            chat_persistence.SETTINGS.geometry = self.wm_geometry()
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

    def post_event(self, ev: "APP_EVENTS", data: Any):
        """
        Post virtual event with data.

        :param ev: APP_EVENT to post
        :param data: data to pass to bind callable
        :return:
        """
        if len(self._bind_table[ev]) == 0:
            logger.warning(f"{ev} not bind")
            return
        self._event_queue.put(EVENT(ev, data))
        self.event_generate(ev.value, when="tail")
        logger.info(f"Post event={ev.name} with data='{str_shortening(str(data))}'")

    def _event(self, ev_cmd):
        def wrapper(event):
            """Decorate bind callable."""
            _data: EVENT = self._event_queue.get()

            q_resp = None
            data = _data.data
            if isinstance(_data.data, ipc_event):
                # this is an event from the IPC client
                q_resp = _data.data.q
                data = _data.data.data

            ret = ev_cmd(data)
            logger.info(
                f"React on={_data.event.name}({ev_cmd.__name__}) with data='{str_shortening(str(data))}': {ret=}"
            )

            if q_resp:
                # send back response to the IPC client
                q_resp.put(ret, block=False)
            return ret

        return wrapper

    def call_assistant(self, data: Dict):
        """
        Call AI assistant in separate thread.

        Post APP_EVENTS.RESP_FROM_ASSISTANT event when response is ready.

        :param data: Query to be answered by assistant
        :return:
        """

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
                ret = AssistantResp(self.conv_id, "", {}, _err)
            self.conv_id = ret.conv_id
            self.post_event(APP_EVENTS.RESP_FROM_ASSISTANT, ret.content)
            self.after_idle(self.status.update_statusbar, ret)

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

    def call_snippet_ipc(self, data: Dict) -> str:
        """
        Call AI snippet in separate thread to transform data and wait for finish.

        :param data: Dict(par0=snippet name, par1=data to transform)
        :return: transformed data
        """

        def _call(snippet, query, result_var):
            # desktop_notify = NotifyWorking(f"ai:{snippet}")
            # desktop_notify.start()
            try:
                ret = self.ai_snippets[snippet].run(query)
            except Exception as e:
                logger.exception(e)
                ret = f"FAIL: {type(e).__name__}: {e}"
            finally:
                # desktop_notify.join()
                pass
            result_var.set(ret)  # set tk result variable which ends inner event loop

        result = tk.Variable(self, None)  # tk variable to handle a thread result
        threading.Thread(
            target=_call,
            args=(data["par0"], data["par1"], result),
            daemon=True,
        ).start()
        self.wait_variable(result)  # enter into tk inner event-loop and wait for result variable
        ret = result.get()
        del result
        return ret


if __name__ == "__main__":
    from dotenv import load_dotenv, find_dotenv

    load_dotenv(find_dotenv())
    app = App()
    app.deiconify()
    app.mainloop()
