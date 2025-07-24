"""KrAIna chat."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from kraina.libs.ipc.client import AppClient
from kraina.libs.notification.MyNotify import notifier_factory
from kraina_chat.base import app_interface


def run_cmd(args):
    if isinstance(args, list) and args[0] == "RUN_SNIPPET_WITH_FILE" and len(args) == 3 and Path(args[2]).is_file():
        # resolve last argument to file path if it is a file
        args[2] = str(Path(args[2]).resolve())
    with AppClient() as client:
        ret = client.send(*args)
        if ret:
            if ret.startswith("FAIL:") or ret.startswith("TIMEOUT"):
                print(ret.encode("utf-8").decode(sys.stdout.encoding, errors="ignore"), flush=True, file=sys.stderr)
            else:
                print(ret.encode("utf-8").decode(sys.stdout.encoding, errors="ignore"), flush=True, file=sys.stdout)


def run_app_and_cmd(args=None):
    if not args:
        args = ["SHOW_APP"]
    try:
        run_cmd(args)
    except ConnectionRefusedError:
        # Application not started, run in the separate process
        # TODO: windows
        # proc_exe = subprocess.Popen(<Your executable path>, shell=True)
        # proc_exe.send_signal(subprocess.signal.SIGTERM)
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            kraina_app_name = "kraina_app.exe" if sys.platform == "win32" else "kraina_app"
            kraina_app_path = Path(sys.argv[0]).parent.resolve() / kraina_app_name
            if not kraina_app_path.exists():
                raise FileNotFoundError(f"Kraina app not found at {kraina_app_path}")
            subprocess.Popen([str(kraina_app_path)], start_new_session=True)
        else:
            subprocess.Popen([sys.executable, Path(__file__).parent / "kraina_app.py"], start_new_session=True)
        # Try to connect to just started application to use IPC
        start = time.time()
        while time.time() <= start + 45.0:
            try:
                run_cmd(args)
            except ConnectionRefusedError:
                time.sleep(0.2)
                continue
            else:
                break


if __name__ == "__main__":
    descr = "KraIna chat application.\nCommands:\n"
    for cmd, cmd_descr in app_interface().items():
        descr += f"\t{cmd} - {cmd_descr}\n"
    descr += "\tNo argument - run GUI app. If app is already run, show it"
    parser = argparse.ArgumentParser(
        prog="kraina_cli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=descr,
        usage="kraina_cli command",
    )
    _, args = parser.parse_known_args()
    if not args:
        run_app_and_cmd()
    else:
        # call IPC command to be executed by Chat application
        with notifier_factory()(f"KrAIna: {args[0]}"):
            run_app_and_cmd(args)
