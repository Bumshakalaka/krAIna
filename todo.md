# TODO List

## Core Tasks
- Implement a notification system for Windows, considering either native OS notifications or a custom tkinter solution.
- Enhance asynchronous processing.
- windows support

## Assistant Enhancements
- Implement memory and vector search capabilities.
- Develop more effective prompts and enable customization.
- Develop way to pass text file as input
- Do _run_ocr_assistant to BaseAssistant to not use overwrite.

## Chat Features
- Enable streaming responses.
- Add clipboard support.
- Develop a settings window for user preferences.
- modify chats history:
  - allow to unhide/show all
  - allow to delete permanent
  - add creation date to description
  - mark conversation permanently visible
- Include a welcome message in the chat window. When we are in new chat, switching between assistants shows description in chat history
- Check spelling in the user query window.
- Persist other settings:
  - size of internal windows
- markdown:
  - better tables handling
  - work with better CSS
  - human message broken, not converted to html properly when punctuation or list used

## Miscellaneous
- Introduce textual inline chat.
- Develop a REST API for external integrations.
- Joplin loader - base on https://python.langchain.com/v0.1/docs/modules/agents/quick_start/
- make toolkit from snippets—in chat, user can ask to fix paragraph or write /fix ... and the tool should be called

# Fixes
- white blank chat history when this widget cleared — NEW CHAT button

# Agents
- 4 steps—reflections, tools, planning, multi-agents
- allow to remove steps from conversation and run it again
- long-term, short-term memory, memories of me