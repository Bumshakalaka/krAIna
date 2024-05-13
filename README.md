## Overview
Set of AI-powered tools for everyday use.

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

## Install
1. Clone the project.
2. Create a virtual environment and install the requirements from requirements.txt.
3. Create a `.env` file and add:
   1. `OPENAI_API_KEY=sk-...` - OpenAI API key

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