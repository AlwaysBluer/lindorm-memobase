#!/usr/bin/env python3
"""
Memory-Enhanced Chatbot Web Server
==================================

FastAPI web server for the memory-enhanced chatbot with streaming support.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from memory_chatbot import MemoryChatbot
from lindormmemobase import Config
from lindormmemobase.models.blob import OpenAICompatibleMessage

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Memory-Enhanced Chatbot", description="AI Assistant with Memory")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global chatbot instances (keyed by session ID)
chatbots: Dict[str, MemoryChatbot] = {}


async def preload_default_chatbot():
    """Preload context for default user to ensure fast first response."""
    default_user_id = "demo_user"
    default_session_id = "preload_session"
    
    logger.info("🔄 Preloading context cache for default user...")
    try:
        # Create and preload chatbot for default user
        await get_or_create_chatbot(default_user_id, default_session_id)
        logger.info("✅ Default context cache preloaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to preload default context cache: {e}")
        # Don't fail server startup if preload fails


class ChatRequest(BaseModel):
    message: str
    user_id: str = "demo_user"
    session_id: str = "default"


class ChatResponse(BaseModel):
    message: str
    timestamp: str
    context_available: bool = False


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_message(self, message: dict, session_id: str):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(json.dumps(message))


manager = ConnectionManager()


async def get_or_create_chatbot(user_id: str, session_id: str) -> MemoryChatbot:
    """Get existing chatbot or create a new one with preloaded context."""
    key = f"{user_id}_{session_id}"
    
    if key not in chatbots:
        # Check if we have a preloaded chatbot for this user that we can reuse/share memory manager
        preload_key = f"{user_id}_preload_session"
        existing_chatbot = chatbots.get(preload_key)
        
        try:
            # Load configuration
            cookbooks_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(os.path.dirname(cookbooks_dir), 'config.yaml')
            
            if os.path.exists(config_path):
                config = Config.from_yaml_file(config_path)
            else:
                config = Config.load_config()
                
            # Create new chatbot
            logger.info(f"Creating new chatbot for user: {user_id}, session: {session_id}")
            chatbot = MemoryChatbot(user_id, config)
            await chatbot.start_memory_worker()
            
            # If we have an existing chatbot with preloaded context, share the memory manager
            if existing_chatbot and session_id != "preload_session":
                logger.info(f"Reusing preloaded memory manager for user: {user_id}")
                # Share the memory manager to benefit from preloaded context
                old_manager = chatbot.memory_manager
                chatbot.memory_manager = existing_chatbot.memory_manager
                # Clean up the old manager
                try:
                    await old_manager.cleanup()
                except:
                    pass
            else:
                # Preload context cache with empty conversation to prepare context buffer
                logger.info(f"Preloading context cache for user: {user_id}")
                try:
                    # Force initial context refresh with empty conversation
                    await chatbot.memory_manager.force_refresh()
                    
                    # Verify context is available
                    context = await chatbot.memory_manager.get_enhanced_context()
                    if context and context.strip():
                        logger.info(f"Context cache preloaded successfully for user {user_id}: {len(context)} chars")
                    else:
                        logger.info(f"No existing memories found for user {user_id}, cache initialized empty")
                        
                except Exception as e:
                    logger.warning(f"Failed to preload context cache for user {user_id}: {e}")
                    # Don't fail the entire chatbot creation if preload fails
            
            chatbots[key] = chatbot
            logger.info(f"Chatbot ready for user: {user_id}, session: {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to create chatbot: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create chatbot: {e}")
    
    return chatbots[key]


@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Serve the chat interface HTML."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    else:
        # Inline HTML if static file doesn't exist
        return HTMLResponse(content=get_inline_html())


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat."""
    await manager.connect(websocket, session_id)
    
    # Initialize user_id with default value to avoid UnboundLocalError
    user_id = "demo_user"
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_message = message_data.get("message", "")
            user_id = message_data.get("user_id", "demo_user")  # Update user_id from message
            
            if not user_message.strip():
                continue
                
            # Get chatbot instance
            try:
                chatbot = await get_or_create_chatbot(user_id, session_id)
            except Exception as e:
                await manager.send_message({
                    "type": "error",
                    "message": str(e)
                }, session_id)
                continue
            
            # Send typing indicator
            await manager.send_message({
                "type": "typing",
                "message": "AI is thinking..."
            }, session_id)
            
            try:
                # Get memory-enhanced context
                context = ""
                if chatbot.memory_enhancement_enabled:
                    context = await chatbot.get_enhanced_context(user_message)
                
                # Send context info
                await manager.send_message({
                    "type": "context",
                    "has_context": bool(context and context.strip()),
                    "context_preview": context[:200] + "..." if len(context) > 200 else context
                }, session_id)
                
                # Generate streaming response
                response_parts = []
                
                # Start streaming response
                await manager.send_message({
                    "type": "response_start"
                }, session_id)
                
                # Use chatbot's streaming method
                try:
                    from lindormmemobase.llm.complete import llm_stream_complete
                    
                    # Build system prompt
                    system_prompt = f"""You are a helpful AI assistant with memory capabilities. 
                    
{context}

Based on the above context about the user, provide personalized and contextually aware responses. 
Use the memory information to make your responses more relevant and helpful.
Be natural and conversational, and refer to remembered information when appropriate."""

                    # Recent history for context
                    recent_history = chatbot.conversation_history[-6:]
                    conversation_context = "\n".join([f"{m.role}: {m.content}" for m in recent_history])
                    
                    full_system_prompt = system_prompt
                    if conversation_context:
                        full_system_prompt += f"\n\nRecent conversation:\n{conversation_context}"
                    
                    # Stream the response
                    async for chunk in llm_stream_complete(
                        prompt=user_message,
                        system_prompt=full_system_prompt,
                        temperature=0.7,
                        config=chatbot.memobase.config
                    ):
                        response_parts.append(chunk)
                        await manager.send_message({
                            "type": "response_chunk",
                            "chunk": chunk
                        }, session_id)
                    
                    full_response = "".join(response_parts)
                    
                except Exception as e:
                    logger.warning(f"LLM streaming error: {e}")
                    # Fallback response
                    full_response = chatbot._generate_fallback_response(user_message, context)
                    await manager.send_message({
                        "type": "response_chunk",
                        "chunk": full_response
                    }, session_id)
                
                # Send response complete
                await manager.send_message({
                    "type": "response_complete",
                    "full_response": full_response
                }, session_id)
                
                # Add to conversation history
                chatbot.conversation_history.append(
                    OpenAICompatibleMessage(role="user", content=user_message)
                )
                chatbot.conversation_history.append(
                    OpenAICompatibleMessage(role="assistant", content=full_response)
                )
                
                # Update memory manager
                chatbot.memory_manager.update_conversation_history(user_message, full_response)
                
                # Queue memory extraction if needed
                if chatbot.should_extract_memories():
                    batch_start = max(0, len(chatbot.conversation_history) - chatbot.conversation_batch_size * 2)
                    conversation_batch = chatbot.conversation_history[batch_start:]
                    chatbot.queue_memory_extraction(conversation_batch)
                    
                    await manager.send_message({
                        "type": "memory_extraction",
                        "status": "queued"
                    }, session_id)
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await manager.send_message({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                }, session_id)
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        
        # Clean up chatbot if needed - search for any chatbots related to this session
        logger.info(f"WebSocket disconnected for session: {session_id}")
        
        # Try to clean up using the known user_id first
        key = f"{user_id}_{session_id}"
        if key in chatbots:
            try:
                await chatbots[key].stop_memory_worker()
                await chatbots[key].memory_manager.cleanup()
                del chatbots[key]
                logger.info(f"Cleaned up chatbot for user: {user_id}, session: {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up chatbot {key}: {e}")
        else:
            # If direct key lookup fails, search for any chatbot with this session_id
            keys_to_remove = [k for k in chatbots.keys() if k.endswith(f"_{session_id}")]
            for key in keys_to_remove:
                try:
                    await chatbots[key].stop_memory_worker()
                    await chatbots[key].memory_manager.cleanup()
                    del chatbots[key]
                    logger.info(f"Cleaned up orphaned chatbot: {key}")
                except Exception as e:
                    logger.error(f"Error cleaning up orphaned chatbot {key}: {e}")
    
    except Exception as e:
        # Handle any other unexpected exceptions
        logger.error(f"Unexpected error in WebSocket endpoint for session {session_id}: {e}")
        manager.disconnect(session_id)
        
        # Still try to cleanup
        try:
            keys_to_remove = [k for k in chatbots.keys() if k.endswith(f"_{session_id}")]
            for key in keys_to_remove:
                try:
                    await chatbots[key].stop_memory_worker()
                    await chatbots[key].memory_manager.cleanup()
                    del chatbots[key]
                    logger.info(f"Cleaned up chatbot after unexpected error: {key}")
                except Exception as cleanup_error:
                    logger.error(f"Error in cleanup after unexpected error: {cleanup_error}")
        except Exception as final_error:
            logger.error(f"Final cleanup failed: {final_error}")


@app.get("/api/memories/{user_id}")
async def get_user_memories(user_id: str):
    """Get user's memories."""
    try:
        # Get any chatbot instance for this user to access memobase
        user_chatbots = [cb for key, cb in chatbots.items() if key.startswith(f"{user_id}_")]
        if not user_chatbots:
            # Create temporary chatbot to access memories
            config = Config.load_config()
            temp_chatbot = MemoryChatbot(user_id, config)
            profiles = await temp_chatbot.memobase.get_user_profiles(user_id)
            await temp_chatbot.memory_manager.cleanup()
        else:
            chatbot = user_chatbots[0]
            profiles = await chatbot.memobase.get_user_profiles(user_id)
        
        # Format profiles for display
        formatted_profiles = []
        for profile in profiles:
            formatted_profiles.append({
                "topic": profile.topic,
                "subtopics": {
                    subtopic: {
                        "content": entry.content,
                        "last_updated": entry.last_updated
                    }
                    for subtopic, entry in profile.subtopics.items()
                }
            })
        
        return {"profiles": formatted_profiles}
        
    except Exception as e:
        logger.error(f"Error getting memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/context/{user_id}/{session_id}")
async def get_current_context(user_id: str, session_id: str):
    """Get current context from memory manager."""
    key = f"{user_id}_{session_id}"
    
    # Try to find any chatbot for this user
    chatbot = None
    if key in chatbots:
        chatbot = chatbots[key]
    else:
        # Look for any chatbot with this user_id (including preload session)
        for chatbot_key, cb in chatbots.items():
            if chatbot_key.startswith(f"{user_id}_"):
                chatbot = cb
                break
    
    if not chatbot:
        raise HTTPException(status_code=404, detail="No active session found for user")
    
    try:
        # Get context from memory manager
        context = await chatbot.memory_manager.get_enhanced_context()
        
        # Get cache stats for additional info
        cache_stats = chatbot.memory_manager.get_cache_stats()
        
        return {
            "context": context.strip() if context else "",
            "context_length": len(context.strip()) if context else 0,
            "has_context": bool(context and context.strip()),
            "cache_stats": cache_stats,
            "user_id": user_id,
            "session_id": session_id,
            "buffer_last_update": chatbot.memory_manager.buffer_last_update
        }
        
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/{user_id}/{session_id}")
async def get_session_stats(user_id: str, session_id: str):
    """Get session statistics."""
    key = f"{user_id}_{session_id}"
    if key not in chatbots:
        raise HTTPException(status_code=404, detail="Session not found")
    
    chatbot = chatbots[key]
    
    try:
        profiles = await chatbot.memobase.get_user_profiles(user_id)
        profile_count = len(profiles)
        total_entries = sum(len(p.subtopics) for p in profiles)
        
        cache_stats = chatbot.memory_manager.get_cache_stats()
        
        return {
            "user_id": user_id,
            "session_id": session_id,
            "messages_exchanged": len(chatbot.conversation_history),
            "memory_enhancement": chatbot.memory_enhancement_enabled,
            "memory_profiles": f"{profile_count} topics, {total_entries} entries",
            "cache_stats": cache_stats,
            "session_start": chatbot.session_start.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_inline_html():
    """Return inline HTML for the chat interface."""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memory-Enhanced Chatbot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .chat-container {
            width: 90%;
            max-width: 800px;
            height: 90vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            padding: 20px;
            text-align: center;
            position: relative;
        }
        
        .chat-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .chat-subtitle {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .status-indicator {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            font-size: 12px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
            background: #4CAF50;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        
        .message {
            margin-bottom: 20px;
            display: flex;
            align-items: flex-start;
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 18px;
            font-size: 14px;
            line-height: 1.4;
        }
        
        .message.user .message-content {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            margin-right: 12px;
        }
        
        .message.bot .message-content {
            background: white;
            color: #333;
            margin-left: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .message-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 600;
        }
        
        .message.user .message-avatar {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        
        .message.bot .message-avatar {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
        }
        
        .typing-indicator {
            display: none;
            padding: 12px 16px;
            background: white;
            border-radius: 18px;
            margin-left: 44px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .typing-dots {
            display: flex;
            align-items: center;
        }
        
        .typing-dots span {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #999;
            margin: 0 2px;
            animation: typing 1.5s infinite ease-in-out;
        }
        
        .typing-dots span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-dots span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }
        
        .context-indicator {
            display: none;
            background: #e3f2fd;
            color: #1976d2;
            padding: 8px 12px;
            border-radius: 12px;
            font-size: 12px;
            margin: 10px 20px;
            border-left: 3px solid #2196F3;
        }
        
        .chat-input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
        }
        
        .chat-input-form {
            display: flex;
            align-items: center;
            background: #f5f5f5;
            border-radius: 25px;
            padding: 5px;
        }
        
        .chat-input {
            flex: 1;
            border: none;
            outline: none;
            padding: 12px 16px;
            background: transparent;
            font-size: 14px;
            border-radius: 20px;
        }
        
        .chat-send-btn {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .chat-send-btn:hover {
            transform: scale(1.1);
        }
        
        .chat-send-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 20px;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #666;
        }
        
        .toolbar-buttons {
            display: flex;
            gap: 10px;
        }
        
        .toolbar-btn {
            background: none;
            border: 1px solid #ddd;
            border-radius: 15px;
            padding: 5px 12px;
            cursor: pointer;
            font-size: 11px;
            transition: all 0.2s;
        }
        
        .toolbar-btn:hover {
            background: #e0e0e0;
        }
        
        /* Responsive */
        @media (max-width: 600px) {
            .chat-container {
                width: 100%;
                height: 100vh;
                border-radius: 0;
            }
            
            .message-content {
                max-width: 85%;
            }
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <div class="chat-title">🧠 Memory-Enhanced Chatbot</div>
            <div class="chat-subtitle">AI Assistant with Personalized Memory</div>
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span id="connection-status">Connected</span>
            </div>
        </div>
        
        <div id="context-indicator" class="context-indicator">
            💡 <span id="context-text">Memory context available</span>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="message bot">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    Hello! I'm your memory-enhanced AI assistant. I can remember our conversations and provide personalized responses. How can I help you today?
                </div>
            </div>
        </div>
        
        <div id="typing-indicator" class="typing-indicator">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
        
        <div class="chat-input-container">
            <form class="chat-input-form" id="chatForm">
                <input type="text" class="chat-input" id="messageInput" placeholder="Type your message..." autocomplete="off">
                <button type="submit" class="chat-send-btn" id="sendBtn">
                    ➤
                </button>
            </form>
        </div>
        
        <div class="toolbar">
            <div class="toolbar-info">
                <span id="message-count">Messages: 0</span> | 
                <span id="memory-status">Memory: Active</span>
            </div>
            <div class="toolbar-buttons">
                <button class="toolbar-btn" onclick="showMemories()">📚 Memories</button>
                <button class="toolbar-btn" onclick="showContext()">🧠 Context</button>
                <button class="toolbar-btn" onclick="showStats()">📊 Stats</button>
            </div>
        </div>
    </div>

    <script>
        class MemoryChatbot {
            constructor() {
                this.ws = null;
                this.sessionId = this.generateSessionId();
                this.userId = 'demo_user';
                this.messageCount = 0;
                this.currentResponse = '';
                this.isTyping = false;
                
                this.initializeElements();
                this.connect();
            }
            
            generateSessionId() {
                return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            }
            
            initializeElements() {
                this.chatMessages = document.getElementById('chatMessages');
                this.messageInput = document.getElementById('messageInput');
                this.sendBtn = document.getElementById('sendBtn');
                this.chatForm = document.getElementById('chatForm');
                this.connectionStatus = document.getElementById('connection-status');
                this.typingIndicator = document.getElementById('typing-indicator');
                this.contextIndicator = document.getElementById('context-indicator');
                this.contextText = document.getElementById('context-text');
                this.messageCountEl = document.getElementById('message-count');
                
                this.chatForm.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.sendMessage();
                });
                
                this.messageInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.sendMessage();
                    }
                });
            }
            
            connect() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;
                
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onopen = () => {
                    console.log('Connected to chatbot');
                    this.connectionStatus.textContent = 'Connected';
                    this.connectionStatus.style.color = '#4CAF50';
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };
                
                this.ws.onclose = () => {
                    console.log('Disconnected from chatbot');
                    this.connectionStatus.textContent = 'Disconnected';
                    this.connectionStatus.style.color = '#f44336';
                    
                    // Try to reconnect after 3 seconds
                    setTimeout(() => this.connect(), 3000);
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.connectionStatus.textContent = 'Error';
                    this.connectionStatus.style.color = '#f44336';
                };
            }
            
            handleMessage(data) {
                switch(data.type) {
                    case 'typing':
                        this.showTyping();
                        break;
                        
                    case 'context':
                        this.showContext(data.has_context, data.context_preview);
                        break;
                        
                    case 'response_start':
                        this.hideTyping();
                        this.startNewResponse();
                        break;
                        
                    case 'response_chunk':
                        this.appendToResponse(data.chunk);
                        break;
                        
                    case 'response_complete':
                        this.completeResponse();
                        break;
                        
                    case 'memory_extraction':
                        if (data.status === 'queued') {
                            this.showMemoryExtraction();
                        }
                        break;
                        
                    case 'error':
                        this.hideTyping();
                        this.addMessage('bot', `Error: ${data.message}`);
                        break;
                }
            }
            
            sendMessage() {
                const message = this.messageInput.value.trim();
                if (!message || this.isTyping) return;
                
                this.addMessage('user', message);
                this.messageInput.value = '';
                this.messageCount++;
                this.updateMessageCount();
                
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        message: message,
                        user_id: this.userId,
                        session_id: this.sessionId
                    }));
                }
            }
            
            addMessage(role, content) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${role}`;
                
                const avatar = document.createElement('div');
                avatar.className = 'message-avatar';
                avatar.textContent = role === 'user' ? '👤' : '🤖';
                
                const messageContent = document.createElement('div');
                messageContent.className = 'message-content';
                messageContent.textContent = content;
                
                if (role === 'user') {
                    messageDiv.appendChild(messageContent);
                    messageDiv.appendChild(avatar);
                } else {
                    messageDiv.appendChild(avatar);
                    messageDiv.appendChild(messageContent);
                }
                
                this.chatMessages.appendChild(messageDiv);
                this.scrollToBottom();
                
                return messageContent;
            }
            
            startNewResponse() {
                this.currentResponse = '';
                this.currentResponseElement = this.addMessage('bot', '');
                this.isTyping = true;
                this.sendBtn.disabled = true;
            }
            
            appendToResponse(chunk) {
                this.currentResponse += chunk;
                if (this.currentResponseElement) {
                    this.currentResponseElement.textContent = this.currentResponse;
                    this.scrollToBottom();
                }
            }
            
            completeResponse() {
                this.isTyping = false;
                this.sendBtn.disabled = false;
                this.messageCount++;
                this.updateMessageCount();
                this.hideContext();
            }
            
            showTyping() {
                this.typingIndicator.style.display = 'block';
                this.scrollToBottom();
            }
            
            hideTyping() {
                this.typingIndicator.style.display = 'none';
            }
            
            showContext(hasContext, preview) {
                if (hasContext) {
                    this.contextText.textContent = `Memory context: ${preview}`;
                    this.contextIndicator.style.display = 'block';
                } else {
                    this.contextIndicator.style.display = 'none';
                }
            }
            
            hideContext() {
                setTimeout(() => {
                    this.contextIndicator.style.display = 'none';
                }, 3000);
            }
            
            showMemoryExtraction() {
                const indicator = document.createElement('div');
                indicator.className = 'context-indicator';
                indicator.innerHTML = '🧠 <span>Extracting memories from conversation...</span>';
                indicator.style.display = 'block';
                indicator.style.background = '#f3e5f5';
                indicator.style.color = '#7b1fa2';
                indicator.style.borderLeft = '3px solid #9c27b0';
                
                this.chatMessages.parentNode.insertBefore(indicator, this.chatMessages.nextSibling);
                
                setTimeout(() => {
                    indicator.remove();
                }, 5000);
            }
            
            updateMessageCount() {
                this.messageCountEl.textContent = `Messages: ${this.messageCount}`;
            }
            
            scrollToBottom() {
                setTimeout(() => {
                    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
                }, 100);
            }
        }
        
        // Global functions for toolbar buttons
        async function showMemories() {
            try {
                const response = await fetch(`/api/memories/${chatbot.userId}`);
                const data = await response.json();
                
                let content = '<h3>📚 Your Memories</h3><br>';
                if (data.profiles && data.profiles.length > 0) {
                    data.profiles.forEach(profile => {
                        content += `<strong>🏷️ ${profile.topic}</strong><br>`;
                        Object.entries(profile.subtopics).forEach(([subtopic, entry]) => {
                            content += `&nbsp;&nbsp;└── ${subtopic}: ${entry.content}<br>`;
                        });
                        content += '<br>';
                    });
                } else {
                    content += 'No memories stored yet. Chat more to build your memory profile!';
                }
                
                alert(content.replace(/<br>/g, '\\n').replace(/<[^>]*>/g, ''));
            } catch (error) {
                alert('Error loading memories: ' + error.message);
            }
        }
        
        async function showContext() {
            try {
                const response = await fetch(`/api/context/${chatbot.userId}/${chatbot.sessionId}`);
                const data = await response.json();
                
                let content = '🧠 Current Context Buffer\\n\\n';
                
                if (data.has_context) {
                    content += `Context Length: ${data.context_length} characters\\n`;
                    content += `Last Updated: ${data.buffer_last_update ? new Date(data.buffer_last_update * 1000).toLocaleString() : 'Never'}\\n`;
                    content += `Cache Hit Rate: ${data.cache_stats.hit_rate_percent}\\n\\n`;
                    content += '--- Context Content ---\\n';
                    content += data.context;
                } else {
                    content += 'No context currently available.\\n\\n';
                    content += 'Context will be generated automatically as you chat and memories are created.';
                }
                
                // Use a custom modal instead of alert for better display of long content
                showContextModal(content, data);
            } catch (error) {
                alert('Error loading context: ' + error.message);
            }
        }
        
        function showContextModal(content, data) {
            // Create modal overlay
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.7);
                z-index: 10000;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: inherit;
            `;
            
            // Create modal content
            const modalContent = document.createElement('div');
            modalContent.style.cssText = `
                background: white;
                border-radius: 15px;
                padding: 30px;
                max-width: 80%;
                max-height: 80%;
                overflow-y: auto;
                box-shadow: 0 20px 50px rgba(0,0,0,0.3);
                position: relative;
            `;
            
            const header = document.createElement('div');
            header.style.cssText = `
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                border-bottom: 2px solid #f0f0f0;
                padding-bottom: 15px;
            `;
            
            const title = document.createElement('h2');
            title.textContent = '🧠 Current Context Buffer';
            title.style.cssText = 'margin: 0; color: #333; font-size: 24px;';
            
            const closeBtn = document.createElement('button');
            closeBtn.textContent = '✕';
            closeBtn.style.cssText = `
                background: #f44336;
                color: white;
                border: none;
                border-radius: 50%;
                width: 35px;
                height: 35px;
                cursor: pointer;
                font-size: 18px;
                display: flex;
                align-items: center;
                justify-content: center;
            `;
            closeBtn.onclick = () => document.body.removeChild(modal);
            
            header.appendChild(title);
            header.appendChild(closeBtn);
            
            const info = document.createElement('div');
            info.style.cssText = `
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #4CAF50;
            `;
            
            if (data.has_context) {
                info.innerHTML = `
                    <strong>📊 Context Stats:</strong><br>
                    • Length: ${data.context_length} characters<br>
                    • Last Updated: ${data.buffer_last_update ? new Date(data.buffer_last_update * 1000).toLocaleString() : 'Never'}<br>
                    • Cache Hit Rate: ${data.cache_stats.hit_rate_percent}<br>
                    • Cache Hits: ${data.cache_stats.cache_hits}
                `;
            } else {
                info.innerHTML = `
                    <strong>ℹ️ No Context Available</strong><br>
                    Context will be generated automatically as you chat and memories are created.
                `;
            }
            
            const contextContent = document.createElement('div');
            contextContent.style.cssText = `
                background: #f9f9f9;
                padding: 20px;
                border-radius: 8px;
                white-space: pre-wrap;
                font-family: monospace;
                font-size: 14px;
                line-height: 1.4;
                border: 1px solid #e0e0e0;
                max-height: 400px;
                overflow-y: auto;
            `;
            
            if (data.has_context) {
                contextContent.textContent = data.context;
            } else {
                contextContent.innerHTML = '<em style="color: #666;">No context content available</em>';
            }
            
            modalContent.appendChild(header);
            modalContent.appendChild(info);
            if (data.has_context) {
                const contextLabel = document.createElement('h3');
                contextLabel.textContent = '📝 Context Content:';
                contextLabel.style.cssText = 'margin: 0 0 10px 0; color: #333;';
                modalContent.appendChild(contextLabel);
                modalContent.appendChild(contextContent);
            }
            
            modal.appendChild(modalContent);
            document.body.appendChild(modal);
            
            // Close on background click
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                }
            });
        }
        
        async function showStats() {
            try {
                const response = await fetch(`/api/stats/${chatbot.userId}/${chatbot.sessionId}`);
                const data = await response.json();
                
                const stats = [
                    `User ID: ${data.user_id}`,
                    `Session ID: ${data.session_id}`,
                    `Messages: ${data.messages_exchanged}`,
                    `Memory Enhancement: ${data.memory_enhancement ? 'ON' : 'OFF'}`,
                    `Memory Profiles: ${data.memory_profiles}`,
                    `Cache Hit Rate: ${data.cache_stats.hit_rate_percent}`,
                    `Session Start: ${new Date(data.session_start).toLocaleString()}`
                ].join('\\n');
                
                alert('📊 Session Statistics\\n\\n' + stats);
            } catch (error) {
                alert('Error loading stats: ' + error.message);
            }
        }
        
        // Initialize chatbot
        let chatbot;
        window.addEventListener('load', () => {
            chatbot = new MemoryChatbot();
        });
    </script>
</body>
</html>
    """


if __name__ == "__main__":
    import uvicorn
    
    async def startup_event():
        """Startup event to preload context cache."""
        await preload_default_chatbot()
    
    # Add startup event
    app.add_event_handler("startup", startup_event)
    
    print("🚀 Starting Memory-Enhanced Chatbot Web Server...")
    print("📁 Make sure your config.yaml is in the cookbooks/ directory")
    print("🔄 Preloading context cache for faster first response...")
    print("🌐 Web interface will be available at: http://localhost:8000")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )