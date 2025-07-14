@echo OFF
if "%1"=="" (
    cd %~dp0 & .venv\scripts\activate.bat & start "" pythonw chat.py
) else (
    cd %~dp0 & .venv\scripts\activate.bat & python chat.py %* & deactivate
)