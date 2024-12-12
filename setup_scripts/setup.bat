@echo off
set script_dir=%~dp0
REM Navigate to the parent directory of the script directory
cd /d "%script_dir%.."

python -m venv .venv
call .venv\scripts\activate.bat
pip install -r requirements.txt
if not exist .env (
    copy setup_scripts\.env.template .env
)
if not exist config.yaml (
    copy setup_scripts\config.yaml.template config.yaml
) else (
    python setup_scripts\merge_yaml.py config.yaml setup_scripts\config.yaml.template --overwrite "tools.vector-search.model,tools.joplin-search.model"
)

@echo *************************************************
@echo REMEMBER to edit .env file and add your API keys
@echo *************************************************

deactivate