#!/bin/bash

# Start the FastAPI backend server
echo "Starting Contract→606 Intelligence Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
mkdir -p uploads exports

# Start the server
echo "Starting FastAPI server on http://localhost:8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
