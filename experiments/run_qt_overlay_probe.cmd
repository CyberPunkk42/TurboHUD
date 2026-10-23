@echo off
rem Run qt_overlay_probe.py on Windows. The first run sets up PySide6 in a virtual
rem environment in .buildtools\qt-venv (gitignored); later runs reuse it.
rem   experiments\run_qt_overlay_probe.cmd [probe options, e.g. --move --x 200]
rem Needs Python 3.10 or later with the py launcher (python.org installer).
setlocal
set "REPO=%~dp0.."
set "VENV=%REPO%\.buildtools\qt-venv"
set "REQUIREMENTS=%REPO%\experiments\requirements-qt.txt"
if not exist "%VENV%\Scripts\python.exe" (
    echo Setting up Python with Qt in %VENV% ...
    py -3 -m venv "%VENV%" || exit /b 1
)
rem Install again whenever the pinned version changes.
fc /b "%REQUIREMENTS%" "%VENV%\requirements-qt.txt" >nul 2>&1
if errorlevel 1 (
    "%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r "%REQUIREMENTS%" || exit /b 1
    copy /y "%REQUIREMENTS%" "%VENV%\requirements-qt.txt" >nul
)
"%VENV%\Scripts\python.exe" -B "%REPO%\experiments\qt_overlay_probe.py" %*
