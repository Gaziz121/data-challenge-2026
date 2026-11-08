@echo off
rem Двойной клик перед защитой: остановить сервер демо, очистить историю репетиций (спросит YES), запустить чистое демо.
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-demo.ps1" -Reset %*
pause
