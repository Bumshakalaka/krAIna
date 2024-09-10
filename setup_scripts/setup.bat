@echo off
set script_dir=%~dp0
REM Navigate to the parent directory of the script directory
cd /d "%script_dir%.."
cd ..
python -m venv .venv
call .venv\scripts\activate.bat
pip install -r requirements.txt
COPY setup_scripts\.env.template .env
COPY setup_scripts\config.yaml.template config.yaml

@echo *************************************************
@echo REMEMBER to edit .env file and add your API keys
@echo *************************************************

deactivate