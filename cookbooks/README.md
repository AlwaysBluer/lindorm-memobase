# Cookbooks

This directory contains practical examples and recipes for using the lindormmemobase package.

## Featured: Memory-Enhanced Chatbot

The `memory_chatbot.py` is a complete application demonstrating all lindormmemobase capabilities:

### Key Features
🧠 **Smart Memory System** - Automatically extracts and stores memories from conversations
🎯 **Context Enhancement** - Uses memories to provide personalized responses
💬 **Interactive Chat** - Real-time chat with rich command system
📚 **Memory Management** - Search, view, and manage stored memories

### Quick Start
```bash
# Set up environment
cp cookbooks/chatbot.env .env
# Edit .env with your API keys

# Run the chatbot
python cookbooks/memory_chatbot.py --user_id your_name

# Available commands in chat:
# /memories - View stored memories
# /search - Search through memories
# /toggle - Toggle memory enhancement
# /help - Show all commands
```

See `CHATBOT_README.md` for detailed documentation.

## How to Run Examples

1. Make sure you have installed the package:
   ```bash
   pip install -e .
   ```

2. Set up your environment variables:
   ```bash
   cp example.env .env
   # Edit .env with your API keys
   ```

3. Run any example:
   ```bash
   python cookbooks/basic_usage.py
   ```

Each example is self-contained and demonstrates specific features of the lindormmemobase package.