@echo off
rem Script chạy EVA nền cho Task Scheduler (xem deploy\README.md) — không mở cửa sổ terminal
rem tương tác, output được ghi vào logs\eva.log để xem lại khi cần debug.
cd /d "%~dp0.."
if not exist logs mkdir logs
"%~dp0..\venv\Scripts\pythonw.exe" main.py >> logs\eva.log 2>&1
