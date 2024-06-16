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
- Make hidden chats visible.
- Include a welcome message in the chat window. When we are in new chat, switching between assistants shows description in chat history
- Support for markdown in chat history.
- Check spelling in the user query window.
- Persist other settings:
  - size of internal windows

## Miscellaneous
- Introduce textual inline chat.
- Develop a REST API for external integrations.
- Joplin loader - base on https://python.langchain.com/v0.1/docs/modules/agents/quick_start/

# Fixes

# Agents
- 4 steps—reflections, tools, planning, multi-agents
- allow to remove steps from conversation and run it again
- long-term, short-term memory, memories of me