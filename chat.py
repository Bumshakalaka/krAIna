"""KrAIna chat."""
import argparse
import logging
import subprocess
import sys
from pathlib import Path

from chat.base import app_interface
from libs.ipc.client import AppClient
from libs.ipc.host import AppHost


def run_app():
    # Run Chat application.
    # longChain import takes around 900ms. Thus, it's place here to have Client IPC fast
    from dotenv import load_dotenv, find_dotenv
    from chat.chat import App

    load_dotenv(find_dotenv())
    app = App()
    try:
        AppHost(app).start()
        app.deiconify()
        app.mainloop()
    except OSError:
        # The application is already running, so destroy it and show the running one
        app.destroy()
        with AppClient() as client:
            client.send("SHOW_APP")


if __name__ == "__main__":
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    file_handler = logging.FileHandler(Path(__file__).parent / "chat.log")
    console_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[file_handler, console_handler])
    console_handler.setLevel(logging.ERROR)
    descr = "KraIna chat application.\nCommands:\n"
    for cmd, cmd_descr in app_interface().items():
        descr += f"\t{cmd} - {cmd_descr}\n"
    descr += "\tNo argument - run GUI app. If app is already run, show it"
    parser = argparse.ArgumentParser(
        prog="chat.sh",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=descr,
        usage="chat.sh command",
    )
    _, args = parser.parse_known_args()
    if not args or len(args) > 1:
        run_app()
    else:
        try:
            with AppClient() as client:
                client.send(args[0])
        except ConnectionRefusedError:
            # TODO: windows
            # proc_exe = subprocess.Popen(<Your executable path>, shell=True)
            # proc_exe.send_signal(subprocess.signal.SIGTERM)
            subprocess.Popen(["python", __file__], start_new_session=True)
