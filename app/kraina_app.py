from dotenv import find_dotenv, load_dotenv
from ipyc import IPyCHost

from kraina.libs.ipc.host import AppHost

try:
    IPyCHost(port=8998)
except OSError:
    pass
else:
    from kraina_chat.main import App

    load_dotenv(find_dotenv())
    app = App()
    AppHost(app).start()
    app.deiconify()
    app.mainloop()
