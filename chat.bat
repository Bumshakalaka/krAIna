@echo OFF
cd %~dp0 & .venv\scripts\activate.bat & python chat.py %* & deactivate