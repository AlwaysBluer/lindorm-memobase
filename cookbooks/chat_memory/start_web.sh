#!/bin/bash

# Memory-Enhanced Chatbot Launcher Script
# =======================================

echo "🧠 Memory-Enhanced Chatbot Launcher"
echo "===================================="

# Check if we're in the right directory
if [ ! -f "web_server.py" ]; then
    echo "❌ Error: Please run this script from the cookbooks/chat_memory/ directory"
    exit 1
fi

# Check if requirements are installed
echo "📦 Checking dependencies..."
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "⚠️  FastAPI dependencies not found. Installing..."
    pip3 install -r requirements-web.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies. Please install manually:"
        echo "   pip install fastapi uvicorn websockets python-multipart"
        exit 1
    fi
    echo "✅ Dependencies installed successfully"
else
    echo "✅ Dependencies already installed"
fi

# Check for config file
echo "🔧 Checking configuration..."
if [ -f "config.yaml" ]; then
    echo "✅ Found config.yaml"
elif [ -f "../config.yaml" ]; then
    echo "✅ Found ../config.yaml"
else
    echo "⚠️  No config.yaml found. Using environment variables and defaults."
fi

# Check for .env file
if [ -f ".env" ]; then
    echo "✅ Found .env file"
elif [ -f "../.env" ]; then
    echo "✅ Found ../.env file"
else
    echo "⚠️  No .env file found. Make sure to set MEMOBASE_LLM_API_KEY environment variable."
fi

echo ""
echo "🚀 Starting Memory-Enhanced Chatbot Web Server..."
echo "📱 Web Interface: http://localhost:8000"
echo "🔄 Press Ctrl+C to stop"
echo ""

# Start the web server
python3 web_server.py