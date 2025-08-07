#!/usr/bin/env python3
"""
Simple Memory Chatbot
====================

A minimal implementation of memory-enhanced chatbot with streaming output.

Features:
- Direct lindormmemobase API calls
- Streaming response output
- Simple memory extraction
- Basic memory search
- Clear error handling

Usage:
    python cookbooks/simple_chatbot/simple_chatbot.py --user_id user123
"""

import asyncio
import argparse
import os
import sys
import yaml
from datetime import datetime
from typing import List, Optional
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Load environment variables from cookbooks directory
from dotenv import load_dotenv
cookbooks_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(cookbooks_env_path):
    load_dotenv(cookbooks_env_path, override=True)
    print(f"✅ Loaded environment variables from cookbooks/.env")

from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig

# Setup basic logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class SimpleChatbot:
    """
    A simple chatbot implementation with streaming response output.
    """
    
    def __init__(self, user_id: str, config: Optional[Config] = None):
        """Initialize the simple chatbot."""
        self.user_id = user_id
        self.conversation_history: List[OpenAICompatibleMessage] = []
        self.session_start = datetime.now()
        
        # Initialize lindormmemobase
        try:
            self.memobase = LindormMemobase(config)
            # Load ProfileConfig from the same config file or extract from main config
            cookbooks_config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
            if os.path.exists(cookbooks_config_path):
                self.profile_config = ProfileConfig.load_from_file(cookbooks_config_path)
                print(f"✅ Using ProfileConfig from cookbooks/config.yaml")
            else:
                # Fallback: extract profile-related settings from main config
                self.profile_config = ProfileConfig.load_from_config(config)
                print(f"✅ Using ProfileConfig extracted from main Config")
                
            logger.info(f"LindormMemobase initialized successfully for user: {user_id}")
            logger.info(f"ProfileConfig language: {self.profile_config.language}, overwrite_profiles: {bool(self.profile_config.overwrite_user_profiles)}")
        except Exception as e:
            logger.error(f"Failed to initialize LindormMemobase: {e}")
            raise
        
        # Simple settings
        self.auto_extract = True
        self.extract_every_n_messages = 2  # Extract after every 2 exchanges
        
        print(f"\n🔧 Simple Chatbot initialized for user: {user_id}")
        print(f"📝 Auto memory extraction: {'ON' if self.auto_extract else 'OFF'}")
        print("=" * 60)
    
    async def chat_loop(self):
        """Main chat loop - simple and straightforward."""
        print("\n🎯 Starting Simple Chat Session")
        print(f"Available commands:")
        print("  /extract   - Manually extract memories")
        print("  /memories  - Show stored memories") 
        print("  /search    - Search memories")
        print("  /clear     - Clear conversation history")
        print("  /quit      - Exit")
        print("\nType normally to chat!\n")
        
        while True:
            try:
                # Get user input
                user_input = input("👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    if await self.handle_command(user_input):
                        continue
                    else:
                        break  # Quit command
                
                # Process regular chat
                await self.process_message(user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 Chat interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}", exc_info=True)
                print(f"🚨 Error: {e}")
        
        print(f"\n📊 Session Summary:")
        print(f"   Messages: {len(self.conversation_history)}")
        print(f"   Duration: {datetime.now() - self.session_start}")
    
    async def process_message(self, user_message: str):
        """Process a regular chat message."""
        logger.debug(f"Processing message: {user_message}")
        
        try:
            # Generate response with memory context
            context = await self.get_memory_context(user_message)
            
            # Stream response
            print(f"\n🤖 Bot: ", end="", flush=True)
            response = await self.generate_streaming_response(user_message, context)
            print()  # New line after streaming
            
            # Add to conversation history
            self.conversation_history.extend([
                OpenAICompatibleMessage(role="user", content=user_message),
                OpenAICompatibleMessage(role="assistant", content=response)
            ])
            
            # Auto-extract memories if enabled
            if (self.auto_extract and 
                len(self.conversation_history) >= self.extract_every_n_messages and
                len(self.conversation_history) % self.extract_every_n_messages == 0):
                print("\n🧠 Auto-extracting memories...")
                await self.extract_memories()
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            print(f"🚨 Error processing message: {e}")
    
    async def get_memory_context(self, user_message: str) -> str:
        """Get memory context using direct lindormmemobase API calls."""
        logger.debug("Getting memory context...")
        
        try:
            # Create conversation for context
            current_conversation = self.conversation_history + [
                OpenAICompatibleMessage(role="user", content=user_message)
            ]
            
            # Get context using lindormmemobase
            context_result = await self.memobase.get_conversation_context(
                user_id=self.user_id,
                conversation=current_conversation,
                profile_config=self.profile_config,
                max_token_size=1500,
                time_range_in_days=30
            )
            
            logger.debug(f"Context retrieved: {len(context_result)} characters")
            return context_result
                
        except Exception as e:
            logger.error(f"Error getting memory context: {e}", exc_info=True)
            return ""
    
    async def generate_streaming_response(self, user_message: str, context: str) -> str:
        """Generate a streaming response using LLM with memory context."""
        logger.debug("Generating streaming LLM response...")
        
        try:
            # Import LLM streaming completion function
            from lindormmemobase.llm.complete import llm_complete
            
            # Build system prompt with context
            system_prompt = """你是一个友好、有用的AI助手。你能够记住用户的信息并基于这些信息进行个性化回复。

请注意：
- 用自然的方式回复，不要提及技术细节
- 如果有用户的历史信息，请适当地引用但不要过于明显
- 保持对话自然流畅
- 用中文回复"""

            if context.strip():
                system_prompt += f"\n\n用户背景信息：\n{context}"
            
            # Create user prompt
            user_prompt = user_message
            
            # Generate LLM response
            response_result = await llm_complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                config=self.memobase.config,
                model=self.memobase.config.best_llm_model
            )
            
            if response_result.ok():
                full_response = response_result.data()
                print(full_response, end="", flush=True)
            else:
                logger.error(f"LLM completion error: {response_result.msg()}")
                full_response = ""
            
            if full_response:
                logger.debug(f"Streaming response generated successfully: {len(full_response)} chars")
                return full_response.strip()
            else:
                fallback = self._fallback_response(user_message, context)
                print(fallback, end="", flush=True)
                return fallback
                
        except Exception as e:
            logger.error(f"Error generating streaming response: {e}", exc_info=True)
            fallback = self._fallback_response(user_message, context)
            print(fallback, end="", flush=True)
            return fallback
    
    def _fallback_response(self, user_message: str, context: str) -> str:
        """Generate a fallback response when LLM is not available."""
        if context.strip():
            return f"我了解您的一些信息，正在为您提供帮助。关于您的问题：{user_message}"
        else:
            return f"我正在了解您，感谢您的问题：{user_message}"
    
    async def handle_command(self, command: str) -> bool:
        """Handle debug commands."""
        logger.debug(f"Handling command: {command}")
        
        cmd = command[1:].lower().split()[0]
        
        try:
            if cmd == "extract":
                await self.extract_memories()
                return True
                
            elif cmd == "memories":
                await self.show_memories()
                return True
                
            elif cmd == "search":
                query = input("🔍 Enter search query: ").strip()
                if query:
                    await self.search_memories(query)
                return True
                
            elif cmd == "context":
                await self.show_current_context()
                return True

            elif cmd == "quit":
                return False
                
            else:
                print(f"❓ Unknown command: {command}")
                return True
                
        except Exception as e:
            logger.error(f"Error handling command {command}: {e}", exc_info=True)
            print(f"🚨 Command error: {e}")
            return True
    
    async def extract_memories(self):
        """Extract memories from conversation history."""
        logger.debug("Starting memory extraction...")
        
        if len(self.conversation_history) < 2:
            print("📝 Need at least one exchange to extract memories")
            return
        
        try:
            # Create blob from recent conversation
            recent_messages = self.conversation_history[-2:]  # Last 2 exchanges
            
            blob = ChatBlob(
                id=f"debug_chat_{self.user_id}_{int(datetime.now().timestamp())}",
                messages=recent_messages,
                type=BlobType.chat,
                timestamp=int(datetime.now().timestamp())
            )
            
            logger.debug(f"Created ChatBlob with {len(recent_messages)} messages")
            
            # Extract memories using lindormmemobase
            result = await self.memobase.extract_memories(
                user_id=self.user_id,
                blobs=[blob],
                profile_config=self.profile_config
            )
            
            logger.debug(f"Memory extraction result: {result}")
            print("✅ Memories extracted successfully")
            
            # Try to show what was extracted
            if hasattr(result, 'merge_add_result'):
                merge_result = result.merge_add_result
                added = len(merge_result.get('add', []))
                updated = len(merge_result.get('update', []))
                print(f"   📈 {added} new memories, {updated} updated")
                
        except Exception as e:
            logger.error(f"Error in extract_memories: {e}", exc_info=True)
            print(f"🚨 Memory extraction error: {e}")
    
    async def show_memories(self):
        """Show stored memories."""
        logger.debug("Retrieving stored memories...")
        
        try:
            profiles = await self.memobase.get_user_profiles(self.user_id)
            
            if profiles:
                print(f"\n📚 Your Stored Memories ({len(profiles)} topics):")
                print("-" * 50)
                
                for profile in profiles:
                    print(f"\n🏷️  Topic: {profile.topic}")
                    for subtopic, entry in profile.subtopics.items():
                        print(f"   └── {subtopic}: {entry.content}")
            else:
                print("📝 No memories stored yet")
                
        except Exception as e:
            logger.error(f"Error showing memories: {e}", exc_info=True)
            print(f"🚨 Error showing memories: {e}")
    
    async def search_memories(self, query: str):
        """Search memories."""
        logger.debug(f"Searching memories for: {query}")
        
        try:
            # Search profiles
            print(f"\n🔍 Searching for: '{query}'")
            print("-" * 30)
            
            profiles = await self.memobase.search_profiles(
                user_id=self.user_id,
                query=query,
                max_results=5
            )
            
            if profiles:
                print("📋 Found in Profiles:")
                for profile in profiles:
                    print(f"   • {profile.topic}")
                    for subtopic, entry in profile.subtopics.items():
                        print(f"     └── {subtopic}: {entry.content}")
            else:
                print("📋 No matching profiles found")
            
            # Search events
            events = await self.memobase.search_events(
                user_id=self.user_id,
                query=query,
                limit=5
            )
            
            if events:
                print("\n📅 Found in Events:")
                for event in events:
                    similarity = event.get('similarity', 0)
                    content = event['content'][:100] + "..." if len(event['content']) > 100 else event['content']
                    print(f"   • {content} (similarity: {similarity:.2f})")
            else:
                print("📅 No matching events found")
                    
        except Exception as e:
            logger.error(f"Error searching memories: {e}", exc_info=True)
            print(f"🚨 Search error: {e}")
    
    async def show_current_context(self):
        """Show the current memory context."""
        logger.debug("Showing current context...")
        
        if not self.conversation_history:
            print("💭 No conversation history yet")
            return
        
        try:
            # Get context for the last user message
            last_user_msg = None
            for msg in reversed(self.conversation_history):
                if msg.role == "user":
                    last_user_msg = msg.content
                    break
            
            if last_user_msg:
                context = await self.get_memory_context(last_user_msg)
                
                print(f"\n💭 Current Memory Context:")
                print("-" * 40)
                if context.strip():
                    print(context)
                else:
                    print("No memory context available")
            else:
                print("💭 No user messages found")
                
        except Exception as e:
            logger.error(f"Error showing context: {e}", exc_info=True)
            print(f"🚨 Context error: {e}")
    
    def show_debug_info(self):
        """Show debug information."""
        print(f"\n🔧 Debug Information:")
        print("-" * 30)
        print(f"User ID: {self.user_id}")
        print(f"Session started: {self.session_start}")
        print(f"Messages in history: {len(self.conversation_history)}")
        print(f"Auto extract: {self.auto_extract}")
        print(f"Extract frequency: every {self.extract_every_n_messages} messages")
        
        # Show recent messages
        if self.conversation_history:
            print(f"\nRecent messages:")
            for msg in self.conversation_history[-4:]:
                role_icon = "👤" if msg.role == "user" else "🤖"
                content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                print(f"   {role_icon} {msg.role}: {content}")
        
        print(f"\nLog file: simple_chatbot_debug.log")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Simple Chatbot")
    parser.add_argument(
        "--user_id",
        default="user123",
        help="User ID for memory management"
    )
    parser.add_argument(
        "--config",
        help="Path to config file"
    )
    parser.add_argument(
        "--no-auto-extract",
        action="store_true",
        help="Disable automatic memory extraction"
    )
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        # Load configuration
        if args.config and os.path.exists(args.config):
            config = Config.load_config(args.config)
        else:
            # Try to use cookbooks/config.yaml first
            cookbooks_config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
            if os.path.exists(cookbooks_config_path):
                config = Config.from_yaml_file(cookbooks_config_path)
                print(f"✅ Using cookbooks/config.yaml")
            else:
                config = Config.load_config()
        
        print("🔧 Initializing Simple Chatbot...")
        logger.info("Starting simple chatbot session")
        
        # Create chatbot
        chatbot = SimpleChatbot(args.user_id, config)
        
        if args.no_auto_extract:
            chatbot.auto_extract = False
        
        # Start chat session
        await chatbot.chat_loop()
        
    except KeyboardInterrupt:
        print("\n\n👋 Simple chatbot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())