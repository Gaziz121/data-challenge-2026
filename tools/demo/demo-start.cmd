@echo off
rem Double-click: start the CQA demo (no paid calls) and open the browser. Ctrl+C or close the window to stop.
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-demo.ps1" %*
pause
