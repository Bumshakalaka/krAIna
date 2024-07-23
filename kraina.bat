@echo OFF
cd %~dp0 & .venv\scripts\activate.bat & python kraina.py --snippet %1 --text %2 & deactivate