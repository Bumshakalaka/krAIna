**Work in progress**

## Overview
Set of AI tools for everyday use.

## Install
1. Clone project
2. create venv and install requirements.txt
3. create `.env` file and add 
   1. `OPENAI_API_KEY=sk-...` - OpenAI API key

### CopyQ Custom Action Installation

1. Edit & save `copyQ/ai_select.ini` file and:
   * adjust path `~/krAIna/kraina.sh` to your needs
   * Change/remove shortcuts if needed (global shortcut CTRL+SHIFT+1, CopyQ shortcut ALT+RETURN)
2. Open CopyQ and run `Command/Global shortcuts...` <F6>
3. Select `Load Commands...` and import `copyQ/ai_select.ini` file

![ai:select Custom Action](img/CopyQ-command.jpg)

Check also `copyQ/ai_translate.ini` to have the translation skill only as CopyQ Custom Action


## Usage

1. Get all supported skills: `./kraina.sh`
2. Translate: `./kraina.sh translate "Cześć, co słychać u Ciebie?"`
3. Git commit: `./kraina.sh commit "$(git diff --staged --no-prefix -U10)"`


### CopyQ Usage
To use krAIna CopyQ Custom Action **ai:select**:
1. Select text
2. CTRL+SHIFT+1
3. Select skill which you'd like to use, press ENTER
4. When the action finishes, the selected text is replaced with the transformed one.

![KrAIna and CopyQ in action](img/kraina-in-action.gif)

or:
1. Select & copy a text to clipboard
2. open CopyQ
3. right-click on the copied text and select **ai:select** Custom Action (or press ALT+RETURN). 
4. When the action finishes, the selected text is replaced with the transformed one.