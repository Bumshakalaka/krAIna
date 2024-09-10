@echo off
cd %~dp0
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