@echo off
REM Starts both the backend server and the desktop app.
REM Run this from the video-rag-assistant root folder.

echo Starting backend...
start "Backend" cmd /k "cd backend && venv\Scripts\activate && uvicorn main:app --reload"

REM Give the backend a moment to start before the desktop app tries to connect
ping 127.0.0.1 -n 4 >nul

echo Starting desktop app...
start "Desktop" cmd /k "cd desktop && npm start"

echo Both processes launching in separate windows.