**Work in progress**

## Overview
Set of AI tools for everyday use.

## Install
1. Clone project
2. create venv and install requirements.txt
3. create `.env` file and add 
   1. `OPENAI_API_KEY=sk-...` - OpenAI API key
   2. `DECRYPT_KEY=MagiCpRompts` - to decrypt prompts DB. If somebody would like to see the prompts, feel free to install, run, and check.

## Usage

`./main.sh translate "Cześć, co słychać u Ciebie?"`

### CopyQ

1. Open CopyQ and run `Command/Global shortcuts...` F6
2. Configure new Command. Here is an example to translate snippet: ![](img/CopyQ-command.jpg)

Now, you can select & copy a text to clipboard, open CopyQ, right-click on the copied text and select ai:translate. 
When translation is done, CopyQ window is closed and selected text is replaced with translated one