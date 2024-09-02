"""
The macro file is a regular script that can be run like a typical Python script,
but it can also function as a macro within the Chat application.
It must contain a `run()` function, which is the only requirement for it to be executable within the Chat application.
When the macro file is loaded by the Chat application as a module, it inspects the `run()` function to get docstring and parameters + annotations.
Subsequently, when the macro is called, the `run()` function is executed in a daemon thread.
In this mode, the Chat application logger is used.

Communication with the Chat application is facilitated through the `ChatInterface()` class.

Here is an example of macro which:
1. **Environment Setup**:
   - Load environment variables using `load_dotenv(find_dotenv())` - not needed if run by Chat app, required to run as regular script.

2. **Initialization**:
   - Create an instance of `Assistants`.
   - Initialize `ChatInterface` with `silent=True`.

3. **Assistant Configuration**:
   - Retrieve the "echo" assistant from `Assistants`.
   - Set the assistant's `max_tokens` to 2048 and `model` to "gpt-4o-mini" - to show that it's possible

4. **Interact with Chat Interface**:
   - Run an initial query to describe Pokemons.
   - Reload and select the chat based on the response conversation ID.
   - Display the chat in chat application.

5. **Gather Information**:
   - Request markdown tables of Pokemon types, the strongest, and the weakest Pokemons, each followed by selecting the respective chat.

6. **Document Preparation**:
   - Request the assistant to generate an outline for the document.
   - Instruct the assistant to generate the document in chunks, specifying that each chunk should be no longer than 2048 tokens and in markdown format.

7. * Generation Loop**:
   - Continuously request chunks until the `__DONE__` marker is found.
   - Clean and collect each chunk.

8. **File Writing**:
   - Write the collected content to the specified output file.

9. **Final Notification**:
   - Inform the chat about the generated document link.

10. **Return Statement**:
    - Return the absolute path of the generated file.
"""
import logging
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from assistants.base import Assistants
from chat.cli import ChatInterface


def run(out_file: str, doc_type: str = "HTML") -> str:
    """
    Generate an document based on assistant responses and save it to the specified file.

    This function interacts with a chat interface and an assistant to gather information about
    Pokemons, then generates an document containing this information.

    :param out_file: Path to the output file where the document will be saved.
    :param doc_type: Document type
    :return: Path to the generated file.
    :raises FileNotFoundError: If the specified output file path is invalid.
    :raises IOError: If there is an error writing to the file.
    """
    load_dotenv(find_dotenv())

    assistants = Assistants()
    # init communication with Chat app. silent=True means, do not raise exception if Chat app is not running.
    chat = ChatInterface(silent=True)

    llm = assistants["echo"]
    # you can overwrite assistant settings
    llm.max_tokens = 2048
    llm.model = "gpt-4o-mini"

    llm_resp = llm.run("Describe what are the Pokemons")
    chat("RELOAD_CHAT_LIST")  #
    chat("SELECT_CHAT", llm_resp.conv_id)
    chat("SHOW_APP")

    llm.run("Give me All types of pokemons in markdown table with pros and cons of each type", conv_id=llm_resp.conv_id)
    chat("SELECT_CHAT", llm_resp.conv_id)
    llm.run("Give me 5 the strongest pokemons in markdown table with type and powers", conv_id=llm_resp.conv_id)
    chat("SELECT_CHAT", llm_resp.conv_id)
    llm.run("Give me 5 the weakest pokemons in markdown table with type and powers", conv_id=llm_resp.conv_id)
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
        f"""
        Your job from now on is to generate {doc_type} document based on complete context above.
        Generate complete {doc_type} document.
        Return chunks no longer than 2048 tokens in one response.
        I will ask you explicit to generate next chunk of {doc_type} code.
        When the complete document will be generated, return __DONE__.
        IMPORTANT: Each chunk must be markdown code and nothing more

        Do not generate the chunks now, I will ask you to do it.
        """,
        conv_id=llm_resp.conv_id,
    )
    chat("SELECT_CHAT", llm_resp.conv_id)

    html = []
    done = False
    while not done:
        chunk = llm.run(f"Generate next chunk of {doc_type} code", conv_id=llm_resp.conv_id)
        chat("SELECT_CHAT", llm_resp.conv_id)
        # clean the received content
        content = chunk.content.replace("__DONE__", "").strip().split("\n")
        if "```" in content[0]:
            content.pop(0)
        if "```" in content[-1]:
            content.pop(-1)
        html.append("\n".join(content))
        if "__DONE__" in chunk.content:
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
    print(run("pokemon_overview.html"))

    # open the HTML document in default browser
    webbrowser.open(str(Path("pokemon_overview.html").resolve()), new=2, autoraise=True)
