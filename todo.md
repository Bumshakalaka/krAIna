# TODO List

## Core Tasks
- Implement a notification system for Windows, considering either native OS notifications or a custom tkinter solution.
- Enhance asynchronous processing.
- windows support
- common codebase for snippets and assistants

## Assistant Enhancements
- Implement memory and vector search capabilities.
- Develop way to pass text file as input
- Do _run_ocr_assistant to BaseAssistant to not use overwrite.

## Chat Features
- Enable streaming responses.
- Add clipboard support.
- Develop a settings window for user preferences—use https://github.com/JamesStallings/pyro/blob/master/pyro as yaml editor in toplevel window
- Include a welcome message in the chat window. When we are in new chat, switching between assistants shows description in chat history
- Check spelling in the user query window.
- markdown:
  - better tables handling
  - work with better CSS
- Add key accelerators (New Chat, assistant switch)

## Miscellaneous
- Introduce textual inline chat.
- Develop a REST API for external integrations.
- make toolkit from snippets—in chat, user can ask to fix paragraph or write /fix ... and the tool should be called
- speedup internal SQlite DB (one session, lazy commit, indexes, cleanup chats older than 30 days, pragma optimise, normalize tables)
- add sqlite DB versioning and migration 
- Add DB with prompts e.g. "Give me something"

# Fixes
- Fix the scrolling of a chat list when there are not too many chats.
- Use an Ipc Serializaion mechanism
- When application is not running when IPC called, Run application and execute IPC command (Currently, the application is run)

# Agents
- 4 steps—reflections, tools, planning, multi-agents
- allow removing steps from conversation and run it again
- long-term, short-term memory, memories of me

# Sidebar
- add modify time to conversation
- allow sorting by creation/modify time — by default by creation time
- add creation/modification date to description
