#!/bin/bash

# Work Recording Backend Startup Script
# This script sets up and runs the Flask backend

echo "Setting up Work Recording Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please configure .env file with your Google Sheets settings"
fi

# Run the application
echo "Starting Flask application..."
python app.py
