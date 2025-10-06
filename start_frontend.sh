#!/bin/bash

# Start the React frontend development server
echo "Starting Contract→606 Intelligence Frontend..."

# Check if node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Start the React development server
echo "Starting React development server on http://localhost:3000"
cd frontend
npm start
