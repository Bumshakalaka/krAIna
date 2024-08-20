@echo=OFF
python -m venv .venv
call .venv\scripts\activate.bat
pip install -r requirements.txt
copy .env.template .env
copy config.yaml.template config.yaml

@echo *************************************************
@echo REMEMBER to edit .env file and add your API keys
@echo *************************************************

deactivate