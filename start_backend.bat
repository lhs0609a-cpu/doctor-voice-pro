@echo off
cd /d E:\u\doctor-voice-pro\backend
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
pause
