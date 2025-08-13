#!/usr/bin/env python3
"""
Convert CSV conversation data to long-term memory using lindorm-memobase
"""
import asyncio
import csv
import json
from typing import List, Dict, Optional
from datetime import datetime
from lindormmemobase import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig


class ConversationMemoryProcessor:
    """Conversation memory processor"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize processor"""
        if config_path:
            self.memobase = LindormMemobase.from_yaml_file(config_path)
        else:
            # Use default config, auto-load from config.yaml and env vars
            self.memobase = LindormMemobase()
        
        # Configure Chinese profile extraction
        self.profile_config = ProfileConfig(language="zh")
        
    async def process_csv_conversations(
        self, 
        csv_file_path: str, 
        user_id: str = "test_user_1",
        batch_size: int = 5,
        use_buffer: bool = True
    ) -> Dict[str, int]:
        """
        Process conversation data from CSV file
        
        Args:
            csv_file_path: CSV file path
            user_id: User ID
            batch_size: Batch processing size
            use_buffer: Whether to use buffer management
            
        Returns:
            Processing result statistics
        """
        print(f"Starting to process CSV file: {csv_file_path}")
        print(f"User ID: {user_id}")
        print(f"Batch size: {batch_size}")
        print(f"Using buffer: {use_buffer}")
        print("-" * 50)
        
        stats = {
            "total_rows": 0,
            "processed_conversations": 0,
            "error_rows": 0,
            "memory_extractions": 0
        }
        
        conversations_batch = []
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            header = next(reader)  # Skip header
            
            print(f"CSV header: {header}")
            print()
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    stats["total_rows"] += 1
                    
                    # Parse CSV row data
                    conversation_data = self._parse_csv_row(row, row_num)
                    if not conversation_data:
                        stats["error_rows"] += 1
                        continue
                    
                    conversations_batch.append(conversation_data)
                    
                    # Process when batch size reached or file ended
                    if len(conversations_batch) >= batch_size:
                        success = await self._process_conversation_batch(
                            conversations_batch, user_id, use_buffer
                        )
                        if success:
                            stats["processed_conversations"] += len(conversations_batch)
                            stats["memory_extractions"] += 1
                        
                        conversations_batch = []
                        
                        # Show progress
                        print(f"Processed {stats['total_rows']} rows, extracted {stats['memory_extractions']} memories")
                    
                except Exception as e:
                    print(f"Error processing row {row_num}: {e}")
                    stats["error_rows"] += 1
                    continue
        
        # Process remaining conversations
        if conversations_batch:
            success = await self._process_conversation_batch(
                conversations_batch, user_id, use_buffer
            )
            if success:
                stats["processed_conversations"] += len(conversations_batch)
                stats["memory_extractions"] += 1
        
        # If using buffer, process all remaining data
        if use_buffer:
            await self._finalize_buffer_processing(user_id)
        
        return stats
    
    def _parse_csv_row(self, row: List[str], row_num: int) -> Optional[Dict]:
        """
        Parse CSV row data
        
        Args:
            row: CSV row data
            row_num: Row number
            
        Returns:
            Parsed conversation data
        """
        if len(row) < 8:
            print(f"Row {row_num} format incorrect, insufficient columns: {len(row)}")
            return None
        
        try:
            source = row[0]
            timestamp = int(row[1]) if row[1] else None
            topic = row[2]
            request = row[3]
            request_ts = int(row[4]) if row[4] else None
            response = row[5]
            response_ts = int(row[6]) if row[6] else None
            stream_id = row[7]
            
            # Parse request JSON
            try:
                request_data = json.loads(request)
                query = request_data.get("query", "")
                chat_history = request_data.get("chat_history", [])
            except json.JSONDecodeError:
                query = request  # If not JSON, use original text
                chat_history = []
            
            # Check if valid conversation (response is not error message)
            if not response or response.startswith("ERROR:") or "Method Not Allowed" in response:
                return None
            
            return {
                "source": source,
                "timestamp": timestamp,
                "topic": topic,
                "query": query,
                "response": response,
                "chat_history": chat_history,
                "request_ts": request_ts,
                "response_ts": response_ts,
                "stream_id": stream_id,
                "row_num": row_num
            }
            
        except Exception as e:
            print(f"Error parsing row {row_num} data: {e}")
            return None
    
    async def _process_conversation_batch(
        self, 
        conversations: List[Dict], 
        user_id: str,
        use_buffer: bool
    ) -> bool:
        """
        Process conversation batch
        
        Args:
            conversations: List of conversation data
            user_id: User ID
            use_buffer: Whether to use buffer
            
        Returns:
            Whether processing succeeded
        """
        try:
            # Convert conversations to message list
            messages = []
            for conv in conversations:
                # Add user message
                if conv["query"]:
                    messages.append(OpenAICompatibleMessage(
                        role="user",
                        content=conv["query"],
                        created_at=self._timestamp_to_datetime(conv["request_ts"])
                    ))
                
                # Add assistant response
                if conv["response"]:
                    messages.append(OpenAICompatibleMessage(
                        role="assistant", 
                        content=conv["response"],
                        created_at=self._timestamp_to_datetime(conv["response_ts"])
                    ))
                
                # Add chat history (if any)
                for hist_msg in conv.get("chat_history", []):
                    if isinstance(hist_msg, dict) and "role" in hist_msg and "content" in hist_msg:
                        messages.append(OpenAICompatibleMessage(
                            role=hist_msg["role"],
                            content=hist_msg["content"]
                        ))
            
            if not messages:
                return False
            
            # Create chat blob
            chat_blob = ChatBlob(
                messages=messages,
                type=BlobType.chat
            )
            
            if use_buffer:
                # Use buffer management
                blob_id = await self.memobase.add_blob_to_buffer(user_id, chat_blob)
                print(f"Conversation batch added to buffer: {blob_id}")
                
                # Check buffer status
                status = await self.memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
                
                if status["is_full"]:
                    print(f"Buffer full, processing {len(status['buffer_full_ids'])} data blocks...")
                    result = await self.memobase.process_buffer(
                        user_id=user_id,
                        blob_type=BlobType.chat,
                        profile_config=self.profile_config,
                        blob_ids=status["buffer_full_ids"]
                    )
                    
                    if result:
                        print("✓ Buffer processing completed")
                        return True
                    else:
                        print("⚠️ Buffer processing returned empty result")
                        return False
                else:
                    return True  # Successfully added to buffer
            else:
                # Direct memory extraction
                result = await self.memobase.extract_memories(
                    user_id=user_id,
                    blobs=[chat_blob],
                    profile_config=self.profile_config
                )
                
                if result:
                    print(f"✓ Successfully extracted memory, contains {len(messages)} messages")
                    return True
                else:
                    print("⚠️ Memory extraction returned empty result")
                    return False
                
        except Exception as e:
            print(f"Error processing conversation batch: {e}")
            return False
    
    async def _finalize_buffer_processing(self, user_id: str):
        """Finalize buffer processing"""
        try:
            print("\n=== Processing remaining buffer data ===")
            
            # Check buffer status
            status = await self.memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
            
            if status["buffer_full_ids"]:
                print(f"Processing remaining {len(status['buffer_full_ids'])} buffer data blocks...")
                result = await self.memobase.process_buffer(
                    user_id=user_id,
                    blob_type=BlobType.chat,
                    profile_config=self.profile_config
                )
                
                if result:
                    print("✓ Remaining buffer data processing completed")
                else:
                    print("⚠️ Remaining buffer processing returned empty result")
            else:
                print("ℹ️ No remaining buffer data to process")
                
        except Exception as e:
            print(f"Error processing remaining buffer data: {e}")
    
    def _timestamp_to_datetime(self, timestamp: Optional[int]) -> Optional[str]:
        """Convert timestamp to datetime string"""
        if not timestamp:
            return None
        
        try:
            # Handle millisecond timestamp
            if timestamp > 1e12:  # milliseconds
                timestamp = timestamp / 1000
            
            dt = datetime.fromtimestamp(timestamp)
            return dt.isoformat()
        except:
            return None
    
    async def get_user_summary(self, user_id: str) -> Dict:
        """Get user memory summary"""
        try:
            # Get user profiles
            profiles = await self.memobase.get_user_profiles(user_id)
            
            # Get recent events
            events = await self.memobase.get_events(
                user_id=user_id,
                time_range_in_days=30,
                limit=10
            )
            
            return {
                "profiles_count": len(profiles),
                "profiles": [
                    {
                        "topic": profile.topic,
                        "subtopics": {
                            subtopic: entry.content
                            for subtopic, entry in profile.subtopics.items()
                        }
                    }
                    for profile in profiles
                ],
                "events_count": len(events),
                "recent_events": [
                    {
                        "content": event["content"],
                        "created_at": event["created_at"]
                    }
                    for event in events[:5]  # Only show first 5 events
                ]
            }
            
        except Exception as e:
            print(f"Error getting user summary: {e}")
            return {
                "profiles_count": 0,
                "profiles": [],
                "events_count": 0,
                "recent_events": []
            }


async def main():
    """Main function"""
    print("=== Shenlan Conversation Data Memory Extraction ===\n")
    
    # Initialize processor
    try:
        processor = ConversationMemoryProcessor()
        print("✓ Lindorm-memobase initialized successfully")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return
    
    # Set parameters
    csv_file_path = "./data/shenlandata_converted.csv"
    user_id = "test_user_1"
    batch_size = 3  # Process 3 conversations at a time
    use_buffer = True  # Use buffer management
    
    # Check if file exists
    try:
        with open(csv_file_path, 'r') as f:
            pass
        print(f"✓ Found CSV file: {csv_file_path}\n")
    except FileNotFoundError:
        print(f"✗ Cannot find CSV file: {csv_file_path}")
        print("Please run convert_stream_to_text.py first to convert raw data")
        return
    
    # Start processing
    start_time = datetime.now()
    
    try:
        stats = await processor.process_csv_conversations(
            csv_file_path=csv_file_path,
            user_id=user_id,
            batch_size=batch_size,
            use_buffer=use_buffer
        )
        
        # Show processing results
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 50)
        print("Processing completed!")
        print("-" * 30)
        print(f"Total processing time: {processing_time:.2f} seconds")
        print(f"Total rows: {stats['total_rows']}")
        print(f"Successfully processed conversations: {stats['processed_conversations']}")
        print(f"Memory extraction count: {stats['memory_extractions']}")
        print(f"Error rows: {stats['error_rows']}")
        print(f"Success rate: {(stats['processed_conversations'] / max(stats['total_rows'], 1) * 100):.1f}%")
        
        # Get user memory summary
        print(f"\n=== User {user_id} Memory Summary ===")
        summary = await processor.get_user_summary(user_id)
        
        print(f"User profile topics count: {summary['profiles_count']}")
        for profile in summary["profiles"]:
            print(f"\n📝 Topic: {profile['topic']}")
            for subtopic, content in profile["subtopics"].items():
                print(f"   └── {subtopic}: {content}")
        
        print(f"\nEvent records count: {summary['events_count']}")
        if summary["recent_events"]:
            print("Recent events:")
            for event in summary["recent_events"]:
                print(f"   📅 {event['content']}")
        
    except Exception as e:
        print(f"\n✗ Error occurred during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())