@echo off
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv 2>nul || "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv )
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
start "" http://127.0.0.1:5000
.venv\Scripts\python.exe app.py
