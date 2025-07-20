import sys

from dotenv import load_dotenv
from ipyc import IPyCHost

from kraina.libs.ipc.host import AppHost

if getattr(sys, "frozen", False):
    import pyi_splash

try:
    IPyCHost(port=8998)
except OSError:
    if getattr(sys, "frozen", False):
        pyi_splash.close()
else:
    from kraina.libs.paths import ENV_FILE
    from kraina_chat.main import App

    load_dotenv(ENV_FILE)
    app = App()
    AppHost(app).start()
    app.deiconify()
    if getattr(sys, "frozen", False):
        pyi_splash.close()
    app.mainloop()
