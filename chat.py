"""KrAIna chat."""
import argparse
import subprocess
import sys
import time

from chat.base import app_interface
from libs.notification.MyNotify import notifier_factory
from libs.ipc.client import AppClient
from libs.ipc.host import AppHost


def run_app():
    # Run Chat application.
    # longChain import takes around 900ms. Thus, it's place here to have Client IPC fast
    from dotenv import load_dotenv, find_dotenv
    from chat.main import App

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
        # no arguments, spawn a new process with chat application
        subprocess.Popen([sys.executable, __file__, "_RUN_"], start_new_session=True)
    elif args[0] == "_RUN_":
        # run application in this process
        run_app()
    else:
        # call IPC command to be executed by Chat application
        with notifier_factory()(f"ai:{args[0]}"):
            try:
                run_cmd(args)
            except ConnectionRefusedError:
                # Application not started, run in the separate process
                # TODO: windows
                # proc_exe = subprocess.Popen(<Your executable path>, shell=True)
                # proc_exe.send_signal(subprocess.signal.SIGTERM)
                subprocess.Popen([sys.executable, __file__, "_RUN_"], start_new_session=True)

                # Try to connect to just started application to use IPC
                start = time.time()
                while time.time() <= start + 5.0:
                    try:
                        if args[0] not in ["HIDE_APP", "SHOW_APP"]:
                            # Hide application if application was not run on IPC call and the command is not about
                            # HIDE and SHOW app
                            run_cmd(["HIDE_APP"])
                        run_cmd(args)
                    except ConnectionRefusedError:
                        time.sleep(0.2)
                        continue
                    else:
                        break
