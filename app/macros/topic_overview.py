"""Example of macro file.

The macro file is a regular script that can be run like a typical Python script,
but it can also function as a macro within the Chat application.
It must contain a `run()` function, which is the only requirement for it to be executable within the Chat application.
When the macro file is loaded by the Chat application as a module, it inspects the `run()` function to get docstring and
 parameters + annotations.
Subsequently, when the macro is called, the `run()` function is executed in a daemon thread.
In this mode, the Chat application logger is used.

Communication with the Chat application is facilitated through the `ChatInterface()` class.

Here is a concise explanation of the program flow:

1. **Initialization and Setup:**
   - Load environment variables using `load_dotenv(find_dotenv())`.
   - Initialize `Assistants` and a `ChatInterface` with `silent=True` to avoid exceptions if the chat app isn't running.
   - Configure the language model (LLM) settings, specifically `max_tokens` and `model`.

2. **Interaction with the LLM:**
   - Use the LLM to generate a comprehensive description of the given topic. This involves multiple stages:
     - Requesting a brief overview.
     - Asking for a detailed history of the topic.
     - Discussing pros and cons.
     - Including examples, statistics, or anecdotes.
     - Outlining and generating the HTML document based on the gathered context.

3. **HTML Document Generation:**
   - Iteratively request chunks of HTML code from the LLM until the document is complete (`__DONE__` flag).
   - Clean and append each chunk of HTML content to a list.

4. **Finalization:**
   - Write the complete HTML content to the specified output file.
   - Inform the chat app of the document's link for future reference.
   - Return the absolute path of the generated HTML document.

"""

import logging
import sys
import webbrowser
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from kraina.assistants.base import Assistants
from kraina_chat.cli import ChatInterface


def run(topic: str, out_file: str) -> str:
    """Generate a comprehensive HTML document on a given topic.

    This function interacts with an assistant to gather detailed information
    about the topic and generate an HTML document.

    :param topic: The subject matter for the document.
    :param out_file: The file path where the HTML document will be saved.
    :return: The absolute path of the generated HTML document.
    :raises Exception: If there are any issues during the document generation.
    """
    load_dotenv(find_dotenv())

    assistants = Assistants()
    # init communication with Chat app. silent=True means, do not raise exception if Chat app is not running.
    chat = ChatInterface(silent=True)

    llm = assistants["samantha"]
    # you can overwrite assistant settings
    llm.max_tokens = 16384
    llm.model = "B"
    llm.tools = []  # no tools needed for this macro

    llm_resp = llm.run(f"Please provide a comprehensive description of topic: {topic}. Start with a brief overview")
    chat("RELOAD_CHAT_LIST")
    chat("SELECT_CHAT", llm_resp.conv_id)
    chat("SHOW_APP")

    llm.run("delve into the history of the topic, highlighting key events and developments.", conv_id=llm_resp.conv_id)
    chat("SELECT_CHAT", llm_resp.conv_id)
    llm.run(
        "discuss the pros and cons, giving a balanced view of the topic's advantages and disadvantages.",
        conv_id=llm_resp.conv_id,
    )
    chat("SELECT_CHAT", llm_resp.conv_id)
    llm.run("include examples, statistics, or anecdotes to enrich your description", conv_id=llm_resp.conv_id)
    chat("SELECT_CHAT", llm_resp.conv_id)

    llm.run(
        """
        Now it's time to generate document with all the responses I asked already.
        This is very important to enclose all the information, If you think I missed something, add it.

        Think and write down what could be the outline of such document, what must be included and what would be the form.
        """,
        conv_id=llm_resp.conv_id,
    )
    chat("SELECT_CHAT", llm_resp.conv_id)
    llm.run(
        """
        Your job from now on is to generate HTML document based on complete context above.
        Generate complete HTML document.
        Return chunks no longer than 2048 tokens in one response.
        I will ask you explicit to generate next chunk of HTML code.
        When the complete document will be generated, you must return __DONE__.
        IMPORTANT: Each chunk must be markdown code and nothing more

        Do not generate the chunks now, I will ask you to do it.
        """,
        conv_id=llm_resp.conv_id,
    )
    chat("SELECT_CHAT", llm_resp.conv_id)

    html = []
    done = False
    while not done:
        chunk = llm.run("Generate next chunk of HTML code", conv_id=llm_resp.conv_id)
        chat("SELECT_CHAT", llm_resp.conv_id)
        # clean the received content
        content = str(chunk.content).replace("__DONE__", "").strip().split("\n")
        if "```" in content[0]:
            content.pop(0)
        if "```" in content[-1]:
            content.pop(-1)
        html.append("\n".join(content))
        if "__DONE__" in str(chunk.content):
            done = True

    with open(Path(out_file), "w") as fd:
        fd.write("\n".join(html))
    # write into the chat link to file - you can open the link from chat app later on
    llm.run(
        f"link to document: [{Path(out_file).stem}]({Path(out_file).resolve()}). Do nothing with it, just notice this.",
        conv_id=llm_resp.conv_id,
    )
    chat("SELECT_CHAT", llm_resp.conv_id)
    return f"'{Path(out_file).resolve()}' generated"


if __name__ == "__main__":
    # Entry point for regular run of the script.

    logger = logging.getLogger(__name__)
    loggerFormat = "%(asctime)s [%(levelname)8s] [%(name)10s]: %(message)s"
    loggerFormatter = logging.Formatter(loggerFormat)
    loggerLevel = logging.INFO
    console_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(format=loggerFormat, level=loggerLevel, handlers=[console_handler])
    print(run("Hot Wheel toys", "overview.html"))

    # open the HTML document in default browser
    webbrowser.open(str(Path("overview.html").resolve()), new=2, autoraise=True)
