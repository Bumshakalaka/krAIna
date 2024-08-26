@echo off
setlocal enabledelayedexpansion

REM Define the directory to search
set start_dir=%~dp0
REM Loop through directories named 'snippets'
for /f "delims=" %%d in ('dir /B /S /A:D "%start_dir%\snippets" 2^>nul') do (
    set "dirname=%%~nxd"
    if "!dirname:~0,1!" neq "_" if "!dirname!" neq "." if "!dirname!" neq "snippets" (
        set "result=!result!!dirname!,"
    )
)
REM find symlinks and Loop through sub-directories named 'snippets'
for /f "delims=" %%l in ('dir /B /S /A:L "%start_dir%" 2^>nul') do (
    for /f "delims=" %%d in ('dir /B /S /A:D "%%l\snippets" 2^>nul') do (
        set "dirname=%%~nxd"
        if "!dirname:~0,1!" neq "_" if "!dirname!" neq "." if "!dirname!" neq "snippets" (
            set "result=!result!!dirname!,"
        )
    )
)


REM Remove trailing comma if result is not empty
if defined result set "result=!result:~0,-1!"

echo %result%