# TODO List

## Core Tasks
- Enhance asynchronous processing.
- common codebase for snippets and assistants
- divide code into:
  - kraina - core assistant/snippets/tools base (as whl)
  - kraina-chat
  - kraina-api

## Assistant Enhancements
- Implement memory and vector search capabilities.
- Develop way to pass text file as input
- Do _run_ocr_assistant to BaseAssistant to not use overwrite.

## Chat Features
- Enable streaming responses.
- Include a welcome message in the chat window. When we are in new chat, switching between assistants shows description in chat history
- Check spelling in the user query window - already done on spellcheck branch
- Add auto-completion (save what you type, next type—guess what you would like to type) or text expender 
- markdown:
  - better tables handling
  - work with better CSS
  - lazy loading of html, only when widget is visible
- Full-text search:
  - Find in SQLite, switch to the chat and highlight the text
  - https://sqlalchemy-searchable.readthedocs.io/en/latest/quickstart.html
- Switch to Listbox with sidebar (do not use canvas + buttons) - possible speed optimization on Windows
- Fix the scrolling of a chat list when there are not too many chats.
- Currently, the images are stored in conversation DB as base64; maybe it would be better to store them as files
- database switch/selection (also in memory db)

### Sidebar
- add modify time to conversation
- allow sorting by creation/modify time — by default by creation time
- add creation/modification date to description

## Miscellaneous
- Introduce textual inline chat.
- Develop a REST API for external integrations.
- make toolkit from snippets—in chat, user can ask to fix paragraph or write /fix ... and the tool should be called—it could be OK, but for specific tasks, e.g. translate a 300 line of text will use 3x tokens. Once assistant uses them to pass the text to snippet, then snippet and at the end assistant again
- speedup internal SQlite DB (one session, lazy commit, indexes, cleanup chats older than 30 days, pragma optimise, normalize tables)
- add sqlite DB versioning and migration 
- Add DB with prompts e.g. "Give me something"
- Add script to configure CopyQ (function addCommands())
- RUN_SNIPPET_FROM_FILE command to chat.sh
- Use an Ipc Serialization mechanism
- long-term memroy, e.g. Integrate Qdrant
- allow removing steps from conversation and run it again

## Pyinstaller fixes
- subprocess.Popen - use sys.executable
- pyinstaller in venv with `--collect-all tkinterweb`
- sv-ttk exception - check tkHtmlWeb package and look for `get_tkhtml_folder()`
- first run:
  - extract assistants/tools/snippets outside and use them
  - .env
  - config.yaml
  - sqliteDB

## Tools
- add to a vector-search mechanism to iterate through already stored documents
- vector-search - better handling of PDFs, process documents with images

## Fixes:
- token calculation for images
- token calculation for audio
- should user message be f-string like system message? BaseAssistant property maybe? This not the case for chat app 
