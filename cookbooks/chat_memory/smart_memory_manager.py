"""
Simple Memory Manager with Context Buffer
========================================

A simplified memory manager that maintains a context buffer and refreshes
it periodically. This provides fast context access with minimal complexity.

Key Features:
- In-memory context buffer for instant access
- Periodic refresh every 5-6 seconds 
- Background task management
- Simple cache statistics
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

from lindormmemobase.models.blob import OpenAICompatibleMessage

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Simple cache statistics."""
    buffer_hits: int = 0
    buffer_misses: int = 0
    last_refresh: Optional[datetime] = None
    refresh_count: int = 0
    average_response_time: float = 0.0


class SmartMemoryManager:
    """
    Simple memory manager with context buffer and periodic refresh.
    
    Maintains a single context buffer that gets refreshed every 5-6 seconds
    in the background. Provides instant access to cached context.
    """
    
    def __init__(self, user_id: str, memobase, refresh_interval: int = 10):
        self.user_id = user_id
        self.memobase = memobase
        self.refresh_interval = refresh_interval  # seconds
        
        # Context buffer
        self.context_buffer: str = ""
        self.buffer_last_update: Optional[float] = None
        
        # Recent conversation cache for context generation
        self.recent_conversations: List[OpenAICompatibleMessage] = []
        self.max_conversation_history = 8  # Keep last 4 exchanges (8 messages)
        
        # Background task management
        self.refresh_task: Optional[asyncio.Task] = None
        self.is_refreshing = False
        self.should_stop = False
        
        # Statistics
        self.stats = CacheStats()
        
        logger.info(f"SmartMemoryManager initialized for user: {user_id}")
        logger.info(f"Context refresh interval: {refresh_interval}s")
        
        # Start background refresh task
        self.refresh_task = asyncio.create_task(self._background_refresh_worker())
    
    def update_conversation_history(self, user_message: str, assistant_message: str):
        """Update the recent conversation history for context generation."""
        # Add new messages
        self.recent_conversations.append(
            OpenAICompatibleMessage(role="user", content=user_message)
        )
        self.recent_conversations.append(
            OpenAICompatibleMessage(role="assistant", content=assistant_message)
        )
        
        # Keep only recent messages (last N exchanges)
        if len(self.recent_conversations) > self.max_conversation_history:
            self.recent_conversations = self.recent_conversations[-self.max_conversation_history:]
        
        logger.debug(f"Updated conversation history for user {self.user_id}: {len(self.recent_conversations)} messages")
    
    async def get_enhanced_context(self) -> str:
        """
        Get enhanced context from buffer (instant access).
        
        Returns cached context from buffer or empty string if not available.
        """
        start_time = time.time()
        
        try:
            if self.context_buffer:
                self.stats.buffer_hits += 1
                logger.debug(f"Context buffer hit for user: {self.user_id}")
                context = self.context_buffer
                # Log context info without full content to avoid log spam
                logger.info(f"Context buffer hit for user {self.user_id}: {len(context)} chars")
                logger.debug(f"Context content: {context}")
            else:
                self.stats.buffer_misses += 1
                logger.debug(f"Context buffer miss for user: {self.user_id}")
                context = ""
            
            # Update response time stats
            response_time = time.time() - start_time
            self.stats.average_response_time = (
                (self.stats.average_response_time * 0.9) + (response_time * 0.1)
            )
            
            logger.debug(f"Context retrieved in {response_time:.3f}s")
            return context
            
        except Exception as e:
            logger.error(f"Error getting enhanced context: {e}")
            return ""
    
    async def _background_refresh_worker(self):
        """Background worker that periodically refreshes the context buffer."""
        try:
            logger.info(f"Background context refresh started for user: {self.user_id}")
            
            while not self.should_stop:
                try:
                    # Wait for refresh interval, but check stop signal more frequently
                    for i in range(self.refresh_interval):
                        if self.should_stop:
                            logger.info("Background refresh worker received stop signal")
                            return
                        await asyncio.sleep(1)  # Check every second
                    
                    if self.should_stop:
                        break
                    
                    # Refresh context buffer
                    await self._refresh_context_buffer()
                    
                except asyncio.CancelledError:
                    logger.info("Background refresh worker cancelled")
                    return
                except Exception as e:
                    logger.error(f"Error in background refresh worker: {e}")
                    # Wait a bit before retrying to avoid tight error loop
                    if not self.should_stop:
                        await asyncio.sleep(2)
                    
        except asyncio.CancelledError:
            logger.info("Background refresh worker stopped by cancellation")
            return
        except Exception as e:
            logger.error(f"Background refresh worker crashed: {e}")
        finally:
            logger.info(f"Background refresh worker finished for user: {self.user_id}")
    
    async def _refresh_context_buffer(self):
        """Refresh the context buffer with latest user context."""
        if self.is_refreshing:
            logger.debug("Context refresh already in progress, skipping")
            return
            
        self.is_refreshing = True
        start_time = time.time()
        
        try:
            logger.debug(f"Refreshing context buffer for user: {self.user_id}")
            
            # Use recent conversation history for better context
            conversation_for_context = self.recent_conversations[-4:] if len(self.recent_conversations) > 4 else self.recent_conversations
            
            # Get user context using memobase
            context = await self.memobase.get_conversation_context(
                user_id=self.user_id,
                conversation=conversation_for_context,  # Use recent conversation history
                max_token_size=2000,
                time_range_in_days=30
            )
            
            if context and context.strip():
                self.context_buffer = context.strip()
                self.buffer_last_update = time.time()
                self.stats.refresh_count += 1
                self.stats.last_refresh = datetime.now()
                
                refresh_time = time.time() - start_time
                logger.info(f"Context buffer refreshed for user {self.user_id} in {refresh_time:.2f}s")
                logger.debug(f"Context buffer size: {len(self.context_buffer)} chars")
            else:
                # Clear buffer if no context available
                if self.context_buffer:
                    logger.info(f"No context available, clearing buffer for user {self.user_id}")
                    self.context_buffer = ""
                    self.buffer_last_update = time.time()
                
        except Exception as e:
            logger.error(f"Error refreshing context buffer for user {self.user_id}: {e}")
        finally:
            self.is_refreshing = False
    
    async def force_refresh(self):
        """Force an immediate refresh of the context buffer."""
        logger.info(f"Force refreshing context buffer for user: {self.user_id}")
        await self._refresh_context_buffer()
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics."""
        total_requests = self.stats.buffer_hits + self.stats.buffer_misses
        hit_rate = (self.stats.buffer_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "hit_rate_percent": f"{hit_rate:.1f}%",
            "cache_hits": self.stats.buffer_hits,
            "cache_misses": self.stats.buffer_misses,
            "cached_profiles": 1 if self.context_buffer else 0,  # Simple: either has context or not
            "profile_refreshes": self.stats.refresh_count,
            "average_response_time": self.stats.average_response_time,
            "last_profile_update": self.stats.last_refresh
        }
    
    async def cleanup(self):
        """Clean up background tasks and resources."""
        logger.info(f"Cleaning up SmartMemoryManager for user: {self.user_id}")
        
        # Stop background refresh immediately
        self.should_stop = True
        
        if self.refresh_task and not self.refresh_task.done():
            logger.info("Cancelling background refresh task...")
            self.refresh_task.cancel()
            try:
                # Wait for task to actually stop
                await asyncio.wait_for(self.refresh_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Background refresh task stopped")
            except Exception as e:
                logger.warning(f"Error stopping background task: {e}")
        
        # Clear buffer
        self.context_buffer = ""
        self.recent_conversations.clear()
        
        logger.info(f"SmartMemoryManager cleanup completed for user: {self.user_id}")