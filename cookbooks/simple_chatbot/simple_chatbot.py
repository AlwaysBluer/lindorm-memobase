#!/usr/bin/env python3
"""
Simple Memory Chatbot for Debugging
===================================

A minimal implementation of memory-enhanced chatbot without optimizations.
Perfect for debugging the core lindormmemobase functionality.

Features:
- Direct lindormmemobase API calls
- No caching or optimization
- Simple memory extraction
- Basic memory search
- Clear error handling
- Detailed logging for debugging

Usage:
    python cookbooks/simple_chatbot/simple_chatbot.py --user_id debug_user
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.blob import Blob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig

# Setup detailed logging for debugging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simple_chatbot_debug.log')
    ]
)
logger = logging.getLogger(__name__)


class SimpleChatbot:
    """
    A simple chatbot implementation for debugging lindormmemobase functionality.
    No optimizations, no caching - just direct API calls for easy debugging.
    """
    
    def __init__(self, user_id: str, config: Optional[Config] = None):
        """Initialize the simple chatbot."""
        self.user_id = user_id
        self.conversation_history: List[OpenAICompatibleMessage] = []
        self.session_start = datetime.now()
        
        # Initialize lindormmemobase
        try:
            self.memobase = LindormMemobase(config)
            self.profile_config = ProfileConfig()
            logger.info(f"LindormMemobase initialized successfully for user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to initialize LindormMemobase: {e}")
            raise
        
        # Simple settings
        self.auto_extract = True
        self.extract_every_n_messages = 4  # Extract after every 2 exchanges
        
        print(f"\n🔧 Simple Debug Chatbot initialized for user: {user_id}")
        print(f"📝 Auto memory extraction: {'ON' if self.auto_extract else 'OFF'}")
        print(f"🔍 Debug logging: ON (check simple_chatbot_debug.log)")
        print("=" * 60)
    
    async def chat_loop(self):
        """Main chat loop - simple and straightforward."""
        print("\n🎯 Starting Simple Debug Chat Session")
        print("Available commands:")
        print("  /extract   - Manually extract memories")
        print("  /memories  - Show stored memories") 
        print("  /search    - Search memories")
        print("  /context   - Get current context")
        print("  /clear     - Clear conversation history")
        print("  /debug     - Show debug info")
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
        print(f"   Debug log: simple_chatbot_debug.log")
    
    async def process_message(self, user_message: str):
        """Process a regular chat message."""
        logger.debug(f"Processing message: {user_message}")
        
        try:
            # Generate response with memory context
            context = await self.get_memory_context(user_message)
            response = self.generate_simple_response(user_message, context)
            
            print(f"\n🤖 Bot: {response}")
            
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
                max_tokens=1500,
                time_range_days=30
            )
            
            if context_result.ok():
                context = context_result.data()
                logger.debug(f"Context retrieved: {len(context)} characters")
                return context
            else:
                logger.warning(f"Context retrieval failed: {context_result.msg()}")
                return ""
                
        except Exception as e:
            logger.error(f"Error getting memory context: {e}", exc_info=True)
            return ""
    
    def generate_simple_response(self, user_message: str, context: str) -> str:
        """Generate a simple response (fallback since we can't rely on external LLM)."""
        logger.debug("Generating simple response...")
        
        # Simple response logic for debugging
        if context.strip():
            if "tennis" in user_message.lower() and "tennis" in context.lower():
                return "I see you're interested in tennis! Based on what I remember about you, that's definitely something you enjoy."
            elif "food" in user_message.lower() or "eat" in user_message.lower():
                return "Let me think about your food preferences based on what I know about you..."
            else:
                return f"I'm processing your message with the context I have about you. You said: '{user_message}'"
        else:
            return f"I understand you're saying: '{user_message}'. I don't have much context about you yet, but I'm learning!"
    
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
                
            elif cmd == "clear":
                self.conversation_history.clear()
                print("🗑️ Conversation history cleared")
                return True
                
            elif cmd == "debug":
                self.show_debug_info()
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
            conversation_text = "\n".join([
                f"{msg.role.capitalize()}: {msg.content}" 
                for msg in self.conversation_history[-4:]  # Last 2 exchanges
            ])
            
            blob = Blob(
                id=f"debug_chat_{self.user_id}_{int(datetime.now().timestamp())}",
                content=conversation_text,
                type=BlobType.chat,
                timestamp=int(datetime.now().timestamp())
            )
            
            logger.debug(f"Created blob with content: {conversation_text[:100]}...")
            
            # Extract memories using lindormmemobase
            result = await self.memobase.extract_memories(
                user_id=self.user_id,
                blobs=[blob],
                profile_config=self.profile_config
            )
            
            if result.ok():
                data = result.data()
                logger.debug(f"Memory extraction result: {data}")
                print("✅ Memories extracted successfully")
                
                # Try to show what was extracted
                if hasattr(data, 'merge_add_result'):
                    merge_result = data.merge_add_result
                    added = len(merge_result.get('add', []))
                    updated = len(merge_result.get('update', []))
                    print(f"   📈 {added} new memories, {updated} updated")
                
            else:
                logger.error(f"Memory extraction failed: {result.msg()}")
                print(f"❌ Memory extraction failed: {result.msg()}")
                
        except Exception as e:
            logger.error(f"Error in extract_memories: {e}", exc_info=True)
            print(f"🚨 Memory extraction error: {e}")
    
    async def show_memories(self):
        """Show stored memories."""
        logger.debug("Retrieving stored memories...")
        
        try:
            profiles_result = await self.memobase.get_user_profiles(self.user_id)
            
            if profiles_result.ok():
                profiles = profiles_result.data()
                
                if profiles:
                    print(f"\n📚 Your Stored Memories ({len(profiles)} topics):")
                    print("-" * 50)
                    
                    for profile in profiles:
                        print(f"\n🏷️  Topic: {profile.topic}")
                        for subtopic, entry in profile.subtopics.items():
                            print(f"   └── {subtopic}: {entry.content}")
                else:
                    print("📝 No memories stored yet")
                    
            else:
                logger.error(f"Failed to retrieve memories: {profiles_result.msg()}")
                print(f"❌ Failed to retrieve memories: {profiles_result.msg()}")
                
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
            
            profile_result = await self.memobase.search_profiles(
                user_id=self.user_id,
                query=query,
                max_results=5
            )
            
            if profile_result.ok():
                profiles = profile_result.data()
                if profiles:
                    print("📋 Found in Profiles:")
                    for profile in profiles:
                        print(f"   • {profile.topic}")
                        for subtopic, entry in profile.subtopics.items():
                            print(f"     └── {subtopic}: {entry.content}")
                else:
                    print("📋 No matching profiles found")
            
            # Search events
            event_result = await self.memobase.search_events(
                user_id=self.user_id,
                query=query,
                limit=5
            )
            
            if event_result.ok():
                events = event_result.data()
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
    parser = argparse.ArgumentParser(description="Simple Debug Chatbot")
    parser.add_argument(
        "--user_id",
        default="debug_user",
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
            config = Config.load_config()
        
        print("🔧 Initializing Simple Debug Chatbot...")
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
        print("Check simple_chatbot_debug.log for details")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())