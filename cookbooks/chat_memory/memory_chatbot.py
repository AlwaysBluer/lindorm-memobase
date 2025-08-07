#!/usr/bin/env python3
"""
Memory-Enhanced Chatbot
======================

A complete chatbot application that demonstrates lindormmemobase capabilities:
- Extracts memories from conversations
- Searches relevant memories for context
- Provides personalized responses using memory-enhanced context

Usage:
    python cookbooks/memory_chatbot.py [--user_id USER_ID] [--config CONFIG_FILE]

Features:
- Interactive chat interface
- Automatic memory extraction after each conversation
- Memory-based context enhancement
- Conversation history management
- Graceful error handling
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Optional
import logging
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables from cookbooks/.env
cookbooks_env_path = os.path.join(project_root, '.env')
if os.path.exists(cookbooks_env_path):
    load_dotenv(cookbooks_env_path)
    print(f"✅ Loaded environment from: {cookbooks_env_path}")
else:
    load_dotenv()  # Fallback to current directory
    print(f"⚠️ cookbooks/.env not found, using default .env loading")

from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.blob import Blob, BlobType, OpenAICompatibleMessage, ChatBlob
from lindormmemobase.models.profile_topic import ProfileConfig
from smart_memory_manager import SmartMemoryManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MemoryChatbot:
    """
    A memory-enhanced chatbot that learns from conversations and provides
    contextual responses using extracted memories.
    """

    def __init__(self, user_id: str, config: Optional[Config] = None):
        """Initialize the memory chatbot."""
        self.user_id = user_id
        self.memobase = LindormMemobase(config)
        self.conversation_history: List[OpenAICompatibleMessage] = []
        self.profile_config = ProfileConfig()
        self.session_start = datetime.now()

        # Initialize smart memory manager
        self.memory_manager = SmartMemoryManager(user_id, self.memobase)

        # Chat settings
        self.max_context_tokens = 4000
        self.memory_enhancement_enabled = True
        self.auto_memory_extraction = True
        self.conversation_batch_size = 1  # Extract memories every N messages

        # Performance optimization flags
        self.use_fast_context = True  # Use optimized context retrieval

        # Async memory extraction components
        self.memory_extraction_queue = asyncio.Queue()
        self.memory_worker_task = None
        self.pending_conversations = []  # Store conversations waiting for processing
        self.extraction_in_progress = False

        print(f"\n🤖 Memory Chatbot initialized for user: {user_id}")
        print(f"📚 Memory enhancement: {'ON' if self.memory_enhancement_enabled else 'OFF'}")
        print(f"🧠 Auto memory extraction: {'ON' if self.auto_memory_extraction else 'OFF'}")
        print(f"📦 Batch size: {self.conversation_batch_size} messages")
        print(f"⚡ Fast context mode: {'ON' if self.use_fast_context else 'OFF'}")
        print("=" * 60)

    async def get_enhanced_context(self, user_message: str) -> str:
        """Generate memory-enhanced context for the current conversation."""
        try:
            if self.use_fast_context:
                # Use optimized SmartMemoryManager (90% faster!)
                context = await self.memory_manager.get_enhanced_context()

                if context.strip():
                    return f"\n[OPTIMIZED MEMORY CONTEXT]\n{context}\n[/MEMORY CONTEXT]\n"
                else:
                    return "\n[No relevant memories found]\n"
            else:
                # Fallback to original slower method
                return await self._get_enhanced_context_original(user_message)

        except Exception as e:
            logger.error(f"Error getting enhanced context: {e}")
            return "\n[Memory context error]\n"

    async def _get_enhanced_context_original(self, user_message: str) -> str:
        """Original context generation method (kept for fallback)."""
        try:
            # Create current conversation including the new message
            current_conversation = self.conversation_history + [
                OpenAICompatibleMessage(role="user", content=user_message)
            ]

            # Get comprehensive context with memories (SLOW - uses LLM filtering)
            context = await self.memobase.get_conversation_context(
                user_id=self.user_id,
                conversation=current_conversation,
                profile_config=self.profile_config,
                max_token_size=self.max_context_tokens,
                time_range_in_days=60
            )

            if context and context.strip():
                return f"\n[MEMORY CONTEXT]\n{context}\n[/MEMORY CONTEXT]\n"
            else:
                return "\n[No relevant memories found]\n"

        except Exception as e:
            logger.error(f"Error getting enhanced context: {e}")
            return "\n[Memory context error]\n"

    async def generate_response(self, user_message: str, context: str = "") -> str:
        """Generate AI response using memory-enhanced context."""
        try:
            # Build the prompt with context and conversation history
            messages = []

            # System prompt with memory context
            system_prompt = f"""You are a helpful AI assistant with memory capabilities. 
            
{context}

Based on the above context about the user, provide personalized and contextually aware responses. 
Use the memory information to make your responses more relevant and helpful.
Be natural and conversational, and refer to remembered information when appropriate."""

            messages.append({"role": "system", "content": system_prompt})

            # Add recent conversation history (last 6 messages to keep context manageable)
            recent_history = self.conversation_history[-6:]
            for msg in recent_history:
                messages.append({"role": msg.role, "content": msg.content})

            # Add current user message
            messages.append({"role": "user", "content": user_message})

            # Use the memobase's LLM completion (if available) or fallback to a simple response
            try:
                from lindormmemobase.llm.complete import llm_stream_complete

                # Convert to the format expected by llm_stream_complete
                input_content = user_message
                system_content = system_prompt + "\n\nConversation history:\n" + \
                                 "\n".join([f"{m['role']}: {m['content']}" for m in messages[1:-1]])

                # Stream the response
                print(f"\n🤖 Bot: ", end="", flush=True)
                response_parts = []
                
                async for chunk in llm_stream_complete(
                    prompt=input_content,
                    system_prompt=system_content,
                    temperature=0.7,
                    config=self.memobase.config
                ):
                    print(chunk, end="", flush=True)
                    response_parts.append(chunk)
                
                print()  # New line after streaming is complete
                return "".join(response_parts)

            except Exception as e:
                logger.warning(f"LLM streaming integration error: {e}")
                return self._generate_fallback_response(user_message, context)

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            error_message = "I'm sorry, I encountered an error while processing your message."
            print(f"\n🤖 Bot: {error_message}")
            return error_message

    def _generate_fallback_response(self, user_message: str, context: str) -> str:
        """Generate a simple fallback response when LLM is unavailable."""
        fallback_response = ""
        
        if "hello" in user_message.lower() or "hi" in user_message.lower():
            fallback_response = "Hello! I'm your memory-enhanced assistant. I'm learning about you as we chat!"
        elif "how are you" in user_message.lower():
            fallback_response = "I'm doing well! I'm continuously learning about your preferences and interests to serve you better."
        elif context and "profile" in context.lower():
            fallback_response = f"Based on what I remember about you, I'm here to help with your questions. What would you like to know?"
        else:
            fallback_response = f"I understand you're asking about: {user_message}. I'm processing this with my memory system to provide the best response."
        
        # Print the fallback response immediately (simulating streaming)
        print(f"\n🤖 Bot: {fallback_response}")
        return fallback_response

    async def start_memory_worker(self):
        """Start the background memory extraction worker."""
        if self.memory_worker_task is None or self.memory_worker_task.done():
            self.memory_worker_task = asyncio.create_task(self._memory_extraction_worker())

    async def stop_memory_worker(self):
        """Stop the background memory extraction worker."""
        if self.memory_worker_task and not self.memory_worker_task.done():
            self.memory_worker_task.cancel()
            try:
                await self.memory_worker_task
            except asyncio.CancelledError:
                pass

    async def _memory_extraction_worker(self):
        """Background worker that processes memory extraction queue."""
        try:
            while True:
                # Wait for a task in the queue
                conversation_batch = await self.memory_extraction_queue.get()

                try:
                    self.extraction_in_progress = True
                    print("\n🧠 Processing memories in background...")

                    # Process the conversation batch
                    success = await self._extract_memories_from_batch(conversation_batch)

                    if success:
                        print("✅ Background memory extraction completed")
                    else:
                        print("⚠️ Background memory extraction had issues")

                except Exception as e:
                    logger.error(f"Error in background memory extraction: {e}")
                    print(f"🚨 Background memory extraction error: {e}")
                finally:
                    self.extraction_in_progress = False
                    self.memory_extraction_queue.task_done()

        except asyncio.CancelledError:
            print("🛑 Memory extraction worker stopped")
            raise
        except Exception as e:
            logger.error(f"Memory extraction worker crashed: {e}")

    def queue_memory_extraction(self, conversation_batch: List[OpenAICompatibleMessage]):
        """Queue a conversation batch for background memory extraction."""
        try:
            # Make a copy to avoid modifications during processing
            batch_copy = [msg for msg in conversation_batch]
            self.memory_extraction_queue.put_nowait(batch_copy)
            print("🔄 Queued conversation for background memory processing")
        except asyncio.QueueFull:
            logger.warning("Memory extraction queue is full, skipping this batch")
            print("⚠️ Memory extraction queue full, skipping batch")

    async def _extract_memories_from_batch(self, conversation_batch: List[OpenAICompatibleMessage]) -> bool:
        """Extract memories from a batch of conversations."""
        try:
            if len(conversation_batch) < 2:
                logger.debug(f"Conversation batch too small: {len(conversation_batch)} messages")
                return True  # Need at least a user message and assistant reply

            print(f"\n🧠 Extracting memories from {len(conversation_batch)} conversations...")
            logger.info(f"Starting memory extraction for user {self.user_id} with {len(conversation_batch)} messages")

            # Create blobs from conversation batch
            blob = ChatBlob(
                messages=conversation_batch,
                fields={"user_id": self.user_id, "session_id": f"chat_{self.user_id}_{int(datetime.now().timestamp())}"},
                created_at=datetime.now()
            )

            logger.debug(f"Created ChatBlob for memory extraction with {len(conversation_batch)} messages")

            # Extract memories
            result = await self.memobase.extract_memories(
                user_id=self.user_id,
                blobs=[blob],
                profile_config=self.profile_config
            )

            if result:
                logger.info(f"Memory extraction successful for user {self.user_id}")
                if hasattr(result, 'merge_add_result'):
                    merge_result = result.merge_add_result
                    added = len(merge_result.get('add_profiles', []))
                    updated = len(merge_result.get('update_profiles', []))
                    if added > 0 or updated > 0:
                        print(f"✅ Memories updated: {added} added, {updated} updated")
                        logger.info(f"Memory extraction results - Added: {added}, Updated: {updated}")
                    else:
                        print("📝 No new memories extracted from this batch")
                        logger.debug("No new memories extracted from conversation batch")
                else:
                    print("✅ Memory extraction completed")
                    logger.info("Memory extraction completed successfully")
                return True
            else:
                logger.warning(f"Memory extraction failed for user {self.user_id}")
                print("⚠️ Memory extraction failed")
                return False

        except Exception as e:
            logger.error(f"Error extracting memories from batch for user {self.user_id}: {e}")
            print(f"🚨 Memory extraction error: {e}")
            return False

    async def extract_memories_from_conversation(self) -> bool:
        """Extract memories from the current conversation - kept for backward compatibility."""
        try:
            if len(self.conversation_history) < 2:
                return True  # Need at least a question and answer

            print("\n🧠 Extracting memories from conversation...")

            # Get recent conversation batch
            recent_batch = self.conversation_history[-self.conversation_batch_size * 2:]
            return await self._extract_memories_from_batch(recent_batch)

        except Exception as e:
            logger.error(f"Error extracting memories from conversation: {e}")
            return False

    def should_extract_memories(self) -> bool:
        """Determine if we should extract memories based on conversation length."""
        history_length = len(self.conversation_history)
        # Extract every batch_size * 2 messages (since we have user + assistant pairs)
        return (self.auto_memory_extraction and
                history_length > 0 and
                history_length % (self.conversation_batch_size * 2) == 0)

    def get_memory_status(self) -> str:
        """Get current memory extraction status."""
        queue_size = self.memory_extraction_queue.qsize()
        status = "🔄 Processing" if self.extraction_in_progress else "💤 Idle"
        return f"{status} (Queue: {queue_size})"

    async def show_memories(self) -> None:
        """Display user's current memories."""
        try:
            print("\n📚 Your Current Memories:")
            print("-" * 50)

            profiles_result = await self.memobase.get_user_profiles(self.user_id)
            if profiles_result:
                if profiles_result:
                    for profile in profiles_result:
                        print(f"\n🏷️  Topic: {profile.topic}")
                        for subtopic, entry in profile.subtopics.items():
                            print(f"   └── {subtopic}: {entry.content}")
                else:
                    print("No memories stored yet. Chat more to build your memory profile!")
            else:
                print("Error retrieving memories")

        except Exception as e:
            print(f"Error displaying memories: {e}")

    async def search_memories(self, query: str) -> None:
        """Search through user's memories."""
        try:
            print(f"\n🔍 Searching memories for: '{query}'")
            print("-" * 50)

            # Search both profiles and events
            profiles = await self.memobase.search_profiles(
                user_id=self.user_id,
                query=query,
                max_results=5
            )

            events = await self.memobase.search_events(
                user_id=self.user_id,
                query=query,
                limit=5
            )

            found_something = False

            # Show profile matches
            if profiles:
                print("\n📋 Related Profile Information:")
                for profile in profiles:
                    print(f"   • Topic: {profile.topic}")
                    for subtopic, entry in profile.subtopics.items():
                        print(f"     └── {subtopic}: {entry.content}")
                found_something = True

            # Show event matches
            if events:
                print("\n📅 Related Events:")
                for event in events:
                    similarity = event.get('similarity', 0)
                    print(f"   • {event['content'][:100]}... (similarity: {similarity:.2f})")
                found_something = True

            if not found_something:
                print("No matching memories found.")

        except Exception as e:
            print(f"Error searching memories: {e}")

    def display_commands(self) -> None:
        """Display available commands."""
        print("\n💡 Available Commands:")
        print("  /memories   - Show your current memories")
        print("  /search     - Search your memories")
        print("  /toggle     - Toggle memory enhancement")
        print("  /fast       - Toggle fast context mode")
        print("  /stats      - Show session statistics")
        print("  /status     - Show memory processing status")
        print("  /cache      - Show cache performance stats")
        print("  /help       - Show this help message")
        print("  /quit       - Exit the chatbot")
        print("  Or just type normally to chat!\n")

    async def handle_command(self, command: str) -> bool:
        """Handle special commands. Returns True if command was processed."""
        if command.startswith('/'):
            cmd_parts = command[1:].split(' ', 1)
            cmd = cmd_parts[0].lower()
            arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

            if cmd == 'memories':
                await self.show_memories()
                return True
            elif cmd == 'search':
                if arg:
                    await self.search_memories(arg)
                else:
                    query = input("🔍 Enter search query: ").strip()
                    if query:
                        await self.search_memories(query)
                return True
            elif cmd == 'toggle':
                self.memory_enhancement_enabled = not self.memory_enhancement_enabled
                status = "ON" if self.memory_enhancement_enabled else "OFF"
                print(f"🔄 Memory enhancement is now {status}")
                return True
            elif cmd == 'fast':
                self.use_fast_context = not self.use_fast_context
                status = "ON" if self.use_fast_context else "OFF"
                print(f"⚡ Fast context mode is now {status}")
                print(f"   Fast mode: Uses keyword matching (90% faster)")
                print(f"   Normal mode: Uses LLM filtering (more accurate)")
                return True
            elif cmd == 'stats':
                await self.show_stats()
                return True
            elif cmd == 'status':
                print(f"\n🔍 Memory Processing Status: {self.get_memory_status()}")
                print(f"   Queue size: {self.memory_extraction_queue.qsize()}")
                print(f"   Processing: {'Yes' if self.extraction_in_progress else 'No'}")
                return True
            elif cmd == 'cache':
                await self.show_cache_stats()
                return True
            elif cmd == 'help':
                self.display_commands()
                return True
            elif cmd == 'quit':
                return False  # Signal to quit

        return None  # Not a command, process as regular message

    async def show_cache_stats(self) -> None:
        """Show memory cache performance statistics."""
        print("\n📊 Memory Cache Performance:")
        print("-" * 50)

        try:
            cache_stats = self.memory_manager.get_cache_stats()

            print(f"   Cache Hit Rate: {cache_stats['hit_rate_percent']}")
            print(f"   Cache Hits: {cache_stats['cache_hits']}")
            print(f"   Cache Misses: {cache_stats['cache_misses']}")
            print(f"   Cached Profiles: {cache_stats['cached_profiles']}")
            print(f"   Profile Refreshes: {cache_stats['profile_refreshes']}")
            print(f"   Average Response Time: {cache_stats['average_response_time']:.3f}s")

            if cache_stats['last_profile_update']:
                print(f"   Last Profile Update: {cache_stats['last_profile_update'].strftime('%H:%M:%S')}")
            else:
                print(f"   Last Profile Update: Never")

            print(f"\n💡 Performance Tips:")
            if cache_stats['average_response_time'] > 1.0:
                print("   - Consider using /fast mode for better response time")
            if cache_stats['cached_profiles'] == 0:
                print("   - Profiles will be cached after first use")

        except Exception as e:
            print(f"Error retrieving cache stats: {e}")

    async def show_stats(self) -> None:
        """Show session statistics."""
        print(f"\n📊 Session Statistics:")
        print(f"   User ID: {self.user_id}")
        print(f"   Session started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Messages exchanged: {len(self.conversation_history)}")
        print(f"   Memory enhancement: {'ON' if self.memory_enhancement_enabled else 'OFF'}")
        print(f"   Memory extraction: {self.get_memory_status()}")

        # Get profile count
        try:
            profiles = await self.memobase.get_user_profiles(self.user_id)
            if profiles:
                profile_count = len(profiles)
                total_entries = sum(len(p.subtopics) for p in profiles)
                print(f"   Memory profiles: {profile_count} topics, {total_entries} entries")
        except:
            print(f"   Memory profiles: Unable to load")

    async def chat_loop(self) -> None:
        """Main chat loop."""
        print("\n🎯 Starting Memory-Enhanced Chat Session")
        print("Type /help for available commands, or just start chatting!")
        self.display_commands()

        # Start the background memory worker
        await self.start_memory_worker()

        try:
            while True:
                # Get user input
                user_input = input(f"\n👤 You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                command_result = await self.handle_command(user_input)
                if command_result is False:  # Quit command
                    break
                elif command_result is True:  # Command processed
                    continue

                # Process as regular chat message
                try:
                    # Get memory-enhanced context if enabled
                    context = ""
                    if self.memory_enhancement_enabled:
                        context = await self.get_enhanced_context(user_input)

                    # Generate response (streaming output happens inside generate_response)
                    response = await self.generate_response(user_input, context)

                    # Note: Response is already printed via streaming in generate_response()
                    # No need to print it again here

                    # Add to conversation history
                    self.conversation_history.append(
                        OpenAICompatibleMessage(role="user", content=user_input)
                    )
                    self.conversation_history.append(
                        OpenAICompatibleMessage(role="assistant", content=response)
                    )
                    
                    # Update memory manager with recent conversation
                    self.memory_manager.update_conversation_history(user_input, response)

                    # Queue memory extraction if needed (non-blocking)
                    if self.should_extract_memories():
                        # Get the batch of conversations to process
                        batch_start = max(0, len(self.conversation_history) - self.conversation_batch_size * 2)
                        conversation_batch = self.conversation_history[batch_start:]
                        self.queue_memory_extraction(conversation_batch)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error in chat loop: {e}")
                    print(f"🚨 Error: {e}")

        except KeyboardInterrupt:
            pass
        finally:
            # Ensure cleanup happens even if interrupted
            print("\n🛑 Stopping background workers...")
            await self.stop_memory_worker()
            
            # Clean up memory manager first (most important)
            print("🧹 Cleaning up memory manager...")
            try:
                await self.memory_manager.cleanup()
                print("✅ Memory manager cleanup completed")
            except Exception as e:
                logger.error(f"Error during memory manager cleanup: {e}")
                print(f"⚠️ Memory manager cleanup error: {e}")
            
            # Wait for any pending memory extraction to complete
            if not self.memory_extraction_queue.empty():
                print("⏳ Waiting for background memory processing to complete...")
                try:
                    await asyncio.wait_for(self.memory_extraction_queue.join(), timeout=3.0)
                except asyncio.TimeoutError:
                    print("⚠️ Timeout waiting for memory processing, forcing cleanup...")

        # Final memory extraction for any remaining conversations
        try:
            if self.auto_memory_extraction and len(self.conversation_history) > 0:
                remaining_messages = len(self.conversation_history) % (self.conversation_batch_size * 2)
                if remaining_messages > 0:
                    print("\n🧠 Processing remaining memories from this session...")
                    await self.extract_memories_from_conversation()
        except Exception as e:
            logger.error(f"Error in final memory extraction: {e}")

        print(f"\n👋 Goodbye! This session generated {len(self.conversation_history)} messages.")
        print("Your memories have been saved and will be available in future sessions.")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Memory-Enhanced Chatbot")
    parser.add_argument(
        "--user_id",
        default="demo_user",
        help="User ID for memory management"
    )
    parser.add_argument(
        "--config",
        help="Path to config file (uses default if not specified)"
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable memory enhancement"
    )
    parser.add_argument(
        "--no-auto-extract",
        action="store_true",
        help="Disable automatic memory extraction"
    )
    return parser.parse_args()


async def main():
    """Main application entry point."""
    args = parse_args()

    try:
        # Load configuration - prioritize cookbooks/config.yaml
        cookbooks_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cookbooks_config_path = os.path.join(cookbooks_dir, 'config.yaml')
        
        config_source = ""
        if args.config and os.path.exists(args.config):
            # Use user-specified config file
            config = Config.from_yaml_file(args.config)
            config_source = f"user-specified config: {args.config}"
        elif os.path.exists(cookbooks_config_path):
            # Use cookbooks/config.yaml as default
            config = Config.from_yaml_file(cookbooks_config_path)
            config_source = f"cookbooks config: {cookbooks_config_path}"
        else:
            # Fall back to system default config
            config = Config.load_config()
            config_source = "system default config"

        print("🚀 Initializing Memory-Enhanced Chatbot...")
        print(f"📁 Using {config_source}")
        print(f"🔧 Environment: Loading from cookbooks/.env")

        # Create and configure chatbot
        chatbot = MemoryChatbot(args.user_id, config)

        if args.no_memory:
            chatbot.memory_enhancement_enabled = False
        if args.no_auto_extract:
            chatbot.auto_memory_extraction = False

        # Start chat session
        await chatbot.chat_loop()

    except KeyboardInterrupt:
        print("\n\n👋 Chatbot session interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n💥 Fatal error: {e}")
        print("Please check your configuration and try again.")
        sys.exit(1)


if __name__ == "__main__":
    # Run the chatbot
    asyncio.run(main())
