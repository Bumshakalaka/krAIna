"""KrAIna chat."""
import argparse
import subprocess
import sys
import time

from chat.base import app_interface
from libs.MyNotify import NotifyWorking
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


def run_cmd(args):
    with AppClient() as client:
        ret = client.send(*args)
        if ret:
            if ret.startswith("FAIL:") or ret.startswith("TIMEOUT"):
                print(ret, flush=True, file=sys.stderr)
                exit(1)
            else:
                print(ret, flush=True, file=sys.stdout)


if __name__ == "__main__":
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
    if not args:
        run_app()
    else:
        try:
            desktop_notify = NotifyWorking(f"ai:{args[0]}")
            desktop_notify.start()
            run_cmd(args)
        except ConnectionRefusedError:
            # Application not started, run in the seprate process
            # TODO: windows
            # proc_exe = subprocess.Popen(<Your executable path>, shell=True)
            # proc_exe.send_signal(subprocess.signal.SIGTERM)
            subprocess.Popen(["python3", __file__], start_new_session=True)

            # Try to connect to just started application to use IPC
            start = time.time()
            while time.time() <= start + 5.0:
                try:
                    run_cmd(args)
                except ConnectionRefusedError:
                    time.sleep(0.2)
                    continue
                else:
                    break
        finally:
            desktop_notify.join()
