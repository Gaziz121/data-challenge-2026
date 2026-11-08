@echo off
rem Double-click before the defense: stop the demo server, clear rehearsal history (asks YES), start a clean demo.
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-demo.ps1" -Reset %*
pause
