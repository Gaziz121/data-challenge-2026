@echo off
rem Двойной клик: запустить демо CQA (без платных вызовов) и открыть браузер. Остановить: Ctrl+C или закрыть окно.
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-demo.ps1" %*
pause
