"""KrAIna application CLI module.

This module provides command-line interface functionality for the KrAIna
application, allowing users to interact with the application through IPC
commands and manage the application lifecycle.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from kraina.libs.ipc.client import AppClient
from kraina.libs.notification.MyNotify import notifier_factory
from kraina_chat.base import app_interface


def run_cmd(args):
    """Send command to the KrAIna application via IPC and print the result.

    Resolves file paths for RUN_SNIPPET_WITH_FILE commands and sends the
    command to the application through IPC. Outputs the result to stdout
    or stderr depending on the response type.

    Parameters
    ----------
    args : list or tuple
        Command arguments to send to the application. If the first argument
        is "RUN_SNIPPET_WITH_FILE" and the third argument is a file path,
        the path will be resolved to an absolute path.

    Raises
    ------
    ConnectionRefusedError
        If the application is not running and cannot be reached via IPC.

    """
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
    """Run the application if not running and execute the specified command.

    Attempts to send a command to the application via IPC. If the application
    is not running, it starts the application in a separate process and waits
    up to 45 seconds for it to become available before executing the command.

    Parameters
    ----------
    args : list, optional
        Command arguments to send to the application. If None, defaults to
        ["SHOW_APP"] to show the application window.

    Raises
    ------
    FileNotFoundError
        If running as a frozen executable and the application executable
        cannot be found at the expected location.

    """
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
