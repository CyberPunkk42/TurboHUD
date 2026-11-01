@echo off
rem Start TurboHUD from the source folder on Windows. The first run sets up PySide6 in a
rem virtual environment in .buildtools\venv (gitignored); later runs reuse it.
rem   run_turbohud.cmd [--move]
rem Needs Python 3.10 or later with the py launcher (python.org installer).
setlocal
set "REPO=%~dp0."
set "VENV=%REPO%\.buildtools\venv"
set "REQUIREMENTS=%REPO%\requirements.txt"
if not exist "%VENV%\Scripts\python.exe" (
    echo Setting up Python with Qt in %VENV% ...
    py -3 -m venv "%VENV%" || exit /b 1
)
rem Install again whenever the pinned version changes.
fc /b "%REQUIREMENTS%" "%VENV%\requirements.txt" >nul 2>&1
if errorlevel 1 (
    "%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r "%REQUIREMENTS%" || exit /b 1
    copy /y "%REQUIREMENTS%" "%VENV%\requirements.txt" >nul
)
"%VENV%\Scripts\python.exe" -B "%REPO%\launch_turbohud.py" %*
