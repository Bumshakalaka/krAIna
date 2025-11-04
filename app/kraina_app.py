"""Kraina Application."""

import sys

from dotenv import load_dotenv
from ipyc import IPyCHost

from kraina.libs.ipc.host import AppHost

if getattr(sys, "frozen", False):
    import pyi_splash  # type: ignore

try:
    IPyCHost(port=8998)
except OSError:
    if getattr(sys, "frozen", False):
        pyi_splash.close()  # type: ignore
else:
    from kraina.libs.paths import ENV_FILE
    from kraina_chat.main import App

    load_dotenv(ENV_FILE)
    app = App()
    _ipc_host = AppHost(app)
    _ipc_host.start()
    app.deiconify()
    if getattr(sys, "frozen", False):
        pyi_splash.close()  # type: ignore
    try:
        app.mainloop()
    finally:
        # Gracefully stop the IPC host when the application exits
        _ipc_host.stop()
        sys.exit(0)
