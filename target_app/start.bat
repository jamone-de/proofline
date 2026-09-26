@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)
echo Brightshop on http://127.0.0.1:5590
.venv\Scripts\python.exe -m brightshop
