![logo](img/logo.png)
## Overview
Set of AI-powered tools for everyday use with OpenAi or Azure OpenAI LLMs.
1. **Snippets** — the actions that can be performed on selected text.
2. **Assistants** — your own specialized assistants to talk with.
3. **Chat** - Chat GUI application built using tkinter for Assistants and Snippets.

**Currently on available on Linux**

### Snippets
Snippets are actions that can be performed on selected text. 

KrAIna can be easily equipped with new snippets. Check the `snippets` folder. The structure is as follows:
```
snipptes/
├── fix
│     ├── prompt.md - snippet system prompt, required
│     ├── config.yaml - snippet and LLM settings, optional
│     ├── py_module.py - overwrite default behavior of snippet, specialization - must be defined in model.yaml
```

However, AI-powered snippets are nothing without a good user interface to make it possible to use them in any tool. 
One way to boost your work performance is by performing snippets on the clipboard context with a Clipboard manager.

### Assistants
Your personal AI assistant. It can be a causal assistant or prompt engineer or storyteller.
Assistant can be run as one-shot, similar to snippets or can use its memory and remember the conversation.

The assistants have been designed similar to Snippets. Check the `assistants` folder.

### Chat GUI application
Chat GUI application build using tkinter

![Chat main window](img/chat_main.gif)

features:
* Chat with history
* Last 10 chats which can be recalled. They are auto-named and describe
* Assistant selection
* Support for snippets — right-click in user query widget to apply transformation on a text
* Overwrite Assistant settings
* persistence storage on exit
* progress bar to visualize that LLM is working
* status bar
* Inter-process communication. The chat app initiates an IPC host, enabling control, such as assigning a global shortcut to execute `chat.sh SHOW_APP`.

## Install
1. Clone the project.
2. Create a virtual environment and install the requirements from requirements.txt `pip install -r requirements.txt`.
3. Optional: If you'd like to use Chat GUI, please install also requirements for it `pip install -r chat/requirements.txt` 
4. Create a `.env` file and add:
   1. `OPENAI_API_KEY=sk-...` - OpenAI API key
   2. `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` - AzureAI API key if you'd like to use it
---
*Note*:
If the `AZURE_*` environment variable exists, AzureAI is used; otherwise, OpenAI.
---

### [CopyQ](https://github.com/hluk/CopyQ/tree/master) Custom Action Installation

1. Edit and save the `copyQ/ai_select.ini` file:
   * Adjust the path `~/krAIna/kraina.sh` to your needs.
   * Change or remove shortcuts if needed (global shortcut ALT+SHIFT+1, CopyQ shortcut ALT+RETURN).
2. Open CopyQ and go to `Command/Global shortcuts...` <F6>.
3. Select `Load Commands...` and import the `copyQ/ai_select.ini` file.

![ai:select Custom Action](img/CopyQ-command.jpg)

Check also other CopyQ Custom Actions in `copyQ`.

---
*Note*:
1. Tested with CopyQ 7.1.0 (8.0.0 has some problem with main window focus)
2. To get popup notifications (usually on errors), disable `Use native notifications` in CopyQ Preferences...
---

## Usage

### CLI
1. Get all supported snippets: `./kraina.sh`
2. Translate: `./kraina.sh translate "Cześć, co słychać u Ciebie?"`
3. Git commit: `./kraina.sh commit "$(git diff --staged --no-prefix -U10)"`

### CopyQ Usage
To use the krAIna CopyQ Custom Action **ai:select**:
1. Select text.
2. Press ALT+SHIFT+1.
3. Select the snippet you'd like to use and press ENTER.
4. Once the action finishes, the selected text is replaced with the transformed one.

![KrAIna and CopyQ in action](img/kraina-in-action.gif)

Alternatively:
1. Select and copy text to the clipboard.
2. Open CopyQ.
3. Right-click on the copied text and select the **ai:select** Custom Action (or press ALT+RETURN).
4. Once the action finishes, the selected text is replaced with the transformed one.

### Chat

1. Start the application by running `./chat.sh`.
2. Utilize its features.
3. You can also use `./chat.sh COMMAND` to control the application with the following supported commands:
```text
SHOW_APP - Trigger to display the application
HIDE_APP - Trigger to minimize the application
No argument - Run the GUI app. If the app is already running, it will be shown
```
### Code

#### Snippets
```python
from dotenv import load_dotenv, find_dotenv
from snippets.base import Snippets

load_dotenv(find_dotenv())
snippets = Snippets()
action = snippets["fix"]
print(action.run("I'd like to speak something interest"))
```

#### Assistants
```python
from dotenv import load_dotenv, find_dotenv
from assistants.base import Assistants

load_dotenv(find_dotenv())
assistants = Assistants()
# one shot, do not use database
action = assistants["echo"]
ret = action.run("2+2", use_db=False)
print(ret)  # AssistantResp(conv_id=None, data=AIMessage(content='2 + 2 equals 4.', response_metadata=...
# with history
first = action.run("My name is Paul")  # First call without conv_id creates new conversation
print(first)  # AssistantResp(conv_id=3, data=AIMessage(content='Nice to meet you, Paul! How can I assist you today?', response_metadata=...
ret = action.run("What's my name?", conv_id=first.conv_id) # Second call with conv_id
print(ret)  # AssistantResp(conv_id=3, data=AIMessage(content='Your name is Paul.', response_metadata=...
```