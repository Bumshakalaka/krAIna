@echo OFF
REM Parse the script arguments
set "A=%~1"
set "B=%~2"

REM Execute the Python script with appropriate arguments
if "%B%"=="" (
    cd %~dp0 & .venv\scripts\activate.bat & python kraina_cli.py --file "%A%" & deactivate
) else (
    cd %~dp0 & .venv\scripts\activate.bat & python kraina_cli.py --snippet "%A%" --text "%B%" & deactivate
)