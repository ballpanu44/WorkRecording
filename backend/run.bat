@echo off
REM Work Recording Backend Startup Script
REM This script sets up and runs the Flask backend

echo Setting up Work Recording Backend...

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install requirements
echo Installing dependencies...
pip install -r requirements.txt

REM Copy .env if not exists
if not exist ".env" (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Please configure .env file with your Google Sheets settings
)

REM Run the application
echo Starting Flask application...
python app.py
pause
