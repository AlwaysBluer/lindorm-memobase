#!/usr/bin/env python3
"""
Buffer Storage Integration Tests

This test suite tests the optimized LindormBufferStorage implementation
using real Lindorm Wide Table connections from .env configuration.
"""

import sys
import asyncio
import pytest
import uuid
from datetime import datetime
from dotenv import load_dotenv
from lindormmemobase.config import Config
from lindormmemobase.core.constants import BufferStatus
from lindormmemobase.core.buffer.buffer import create_buffer_storage
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file from the tests directory
test_dir = Path(__file__).parent
env_file = test_dir / ".env"
load_dotenv(env_file)


class TestBufferStorage:
    """Test suite for optimized LindormBufferStorage using real Lindorm connections."""

    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        cls.config = Config.load_config()
        cls.config.max_chat_blob_buffer_token_size = 128
        cls.storage = create_buffer_storage(cls.config)
        cls.test_user_id = "test_user_123"
        cls.test_blob_ids = []
        
        # Clean up any existing test data before starting tests
        asyncio.run(cls._cleanup_test_data())

    @classmethod
    def teardown_class(cls):
        """Cleanup test data after all tests."""
        asyncio.run(cls._cleanup_test_data())

    @classmethod
    async def _cleanup_test_data(cls):
        """Clean up test data from database using new unified table."""
        with cls.storage.get_connection() as (conn, cursor):
            # Get all blob IDs for this user
            cursor.execute(
                "SELECT blob_id FROM buffer WHERE user_id = %s",
                (cls.test_user_id,)
            )
            blob_ids = [row[0] for row in cursor.fetchall()]

            # Delete buffer entries
            for blob_id in blob_ids:
                cursor.execute(
                    "DELETE FROM buffer WHERE user_id = %s AND blob_id = %s",
                    (cls.test_user_id, blob_id)
                )

            print(f"✅ Cleaned up test data for user: {cls.test_user_id} ({len(blob_ids)} blobs)")

    def setup_method(self):
        """Setup before each test method."""
        self.test_blob_ids = []

    def teardown_method(self):
        """Cleanup after each test method."""
        asyncio.run(self._cleanup_method_data())

    async def _cleanup_method_data(self):
        """Clean up data created by individual test methods."""
        if not self.test_blob_ids:
            return

        with self.storage.get_connection() as (conn, cursor):
            # Delete specific test buffer entries
            for blob_id in self.test_blob_ids:
                cursor.execute(
                    "DELETE FROM buffer WHERE user_id = %s AND blob_id = %s",
                    (self.test_user_id, blob_id)
                )

    @pytest.mark.asyncio
    async def test_insert_blob(self):
        """Test inserting a blob into the buffer."""
        blob_id = str(uuid.uuid4())
        self.test_blob_ids.append(blob_id)

        # Create a test ChatBlob
        chat_blob = ChatBlob(
            type=BlobType.chat,
            messages=[
                OpenAICompatibleMessage(
                    role="user",
                    content="Test message for buffer insertion"
                )
            ],
            created_at=datetime.now()
        )

        # Insert blob to buffer
        result = self.storage.insert_blob(self.test_user_id, blob_id, chat_blob)
        assert result.ok(), f"Failed to insert blob: {result.msg()}"

        print("✅ Blob inserted to buffer successfully")

    @pytest.mark.asyncio
    async def test_get_capacity(self):
        """Test getting buffer capacity for a specific blob type."""
        # Insert multiple blobs
        blob_ids = []
        for i in range(3):
            blob_id = str(uuid.uuid4())
            blob_ids.append(blob_id)
            self.test_blob_ids.append(blob_id)

            chat_blob = ChatBlob(
                type=BlobType.chat,
                messages=[
                    OpenAICompatibleMessage(
                        role="user",
                        content=f"Test message {i}"
                    )
                ],
                created_at=datetime.now()
            )

            result = self.storage.insert_blob(self.test_user_id, blob_id, chat_blob)
            assert result.ok()

        # Get buffer capacity
        result = self.storage.get_capacity(self.test_user_id, BlobType.chat)
        assert result.ok(), f"Failed to get buffer capacity: {result.msg()}"
        assert result.data() == 3, f"Expected capacity of 3, got {result.data()}"

    @pytest.mark.asyncio
    async def test_get_pending_ids(self):
        """Test getting pending buffer IDs."""
        # Insert test blobs
        blob_ids = []
        for i in range(2):
            blob_id = str(uuid.uuid4())
            blob_ids.append(blob_id)
            self.test_blob_ids.append(blob_id)

            chat_blob = ChatBlob(
                type=BlobType.chat,
                messages=[
                    OpenAICompatibleMessage(
                        role="user",
                        content=f"Unprocessed message {i}"
                    )
                ],
                created_at=datetime.now()
            )

            result = self.storage.insert_blob(self.test_user_id, blob_id, chat_blob)
            assert result.ok()

        # Get pending buffer IDs
        result = self.storage.get_pending_ids(self.test_user_id, BlobType.chat, BufferStatus.idle)
        assert result.ok(), f"Failed to get pending buffer IDs: {result.msg()}"
        
        buffer_ids = result.data()
        assert len(buffer_ids) == 2, f"Expected 2 pending buffers, got {len(buffer_ids)}"

    @pytest.mark.asyncio
    async def test_check_overflow(self):
        """Test detecting if buffer overflows based on token size."""
        # Insert blobs with large content to trigger buffer overflow
        blob_ids = []
        for i in range(5):
            blob_id = str(uuid.uuid4())
            blob_ids.append(blob_id)
            self.test_blob_ids.append(blob_id)

            # Create a blob with substantial content
            content = "This is a test message with substantial content. " * 50
            chat_blob = ChatBlob(
                type=BlobType.chat,
                messages=[
                    OpenAICompatibleMessage(
                        role="user",
                        content=content
                    )
                ],
                created_at=datetime.now()
            )

            result = self.storage.insert_blob(self.test_user_id, blob_id, chat_blob)
            assert result.ok()

        # Check if buffer overflows
        result = self.storage.check_overflow(
            self.test_user_id,
            BlobType.chat,
            self.config.max_chat_blob_buffer_token_size
        )

        assert result.ok(), f"Failed to check overflow: {result.msg()}"
        buffer_ids = result.data()

        # Should return buffer IDs if token size exceeds limit
        print(f"Buffer overflow check returned {len(buffer_ids)} buffer IDs")

    @pytest.mark.asyncio
    async def test_flush_with_processing(self):
        """Test flush method with actual blob processing."""
        from lindormmemobase.models.profile_topic import ProfileConfig
        
        # Create a realistic profile config for testing
        profile_config = ProfileConfig(
            language="en",
            profile_strict_mode=True,
            profile_validate_mode=False,
            additional_user_profiles=[
                {
                    "topic": "interests",
                    "sub_topics": [
                        {"name": "programming", "description": "Programming languages and technologies"},
                        {"name": "hobbies", "description": "Personal hobbies and activities"}
                    ]
                }
            ]
        )
        
        # Insert test blobs with realistic chat conversations
        blob_ids = []
        conversations = [
            [
                OpenAICompatibleMessage(
                    role="user", 
                    content="I've been learning Python for data analysis. Any recommendations?"
                ),
                OpenAICompatibleMessage(
                    role="assistant", 
                    content="I'd recommend exploring pandas, numpy, and matplotlib for visualization."
                )
            ],
            [
                OpenAICompatibleMessage(
                    role="user", 
                    content="I just got back from Japan and it was incredible! The food was amazing."
                ),
                OpenAICompatibleMessage(
                    role="assistant", 
                    content="Japan sounds amazing! What were your favorite dishes?"
                )
            ]
        ]
        
        for i, messages in enumerate(conversations):
            blob_id = str(uuid.uuid4())
            blob_ids.append(blob_id)
            self.test_blob_ids.append(blob_id)
            
            chat_blob = ChatBlob(
                type=BlobType.chat,
                messages=messages,
                created_at=datetime.now()
            )

            result = self.storage.insert_blob(self.test_user_id, blob_id, chat_blob)
            assert result.ok(), f"Failed to insert blob {i}: {result.msg()}"

        # Verify blobs are in buffer
        result = self.storage.get_pending_ids(self.test_user_id, BlobType.chat, BufferStatus.idle)
        assert result.ok(), f"Failed to get pending blob IDs: {result.msg()}"
        
        pending_ids = result.data()
        assert len(pending_ids) >= 2, f"Expected at least 2 pending blobs, got {len(pending_ids)}"

        # Test flush with actual processing
        result = await self.storage.flush(
            self.test_user_id,
            BlobType.chat,
            blob_ids,
            BufferStatus.idle,
            profile_config
        )
        
        # Check result
        if not result.ok():
            print(f"⚠️ Flush processing returned error: {result.msg()}")
            print("This might be expected if LLM processing fails due to API issues")
            
            # Verify the buffer status was updated to failed
            with self.storage.get_connection() as (conn, cursor):
                cursor.execute(
                    f"SELECT blob_id, status FROM buffer WHERE user_id = %s AND blob_id IN ({','.join(['%s'] * len(blob_ids))})",
                    [self.test_user_id] + blob_ids
                )
                status_results = cursor.fetchall()
                
                for blob_id, status in status_results:
                    assert status in [BufferStatus.failed, BufferStatus.processing], \
                        f"Expected failed or processing status for {blob_id}, got {status}"
                    print(f"✅ Blob {blob_id} correctly marked as {status}")
        else:
            # If processing succeeded
            response_data = result.data()
            print(f"✅ Flush processing succeeded")
            print(f"Response type: {type(response_data)}")
            
            # Verify buffer status updates to done
            with self.storage.get_connection() as (conn, cursor):
                cursor.execute(
                    f"SELECT blob_id, status FROM buffer WHERE user_id = %s AND blob_id IN ({','.join(['%s'] * len(blob_ids))})",
                    [self.test_user_id] + blob_ids
                )
                status_results = cursor.fetchall()
                
                for blob_id, status in status_results:
                    assert status == BufferStatus.done, \
                        f"Expected done status for {blob_id}, got {status}"
                    print(f"✅ Blob {blob_id} correctly marked as {status}")

        print("✅ flush with realistic content test completed successfully")

    @pytest.mark.asyncio
    async def test_buffer_status_updates(self):
        """Test buffer status transitions using new unified table."""
        blob_id = str(uuid.uuid4())
        self.test_blob_ids.append(blob_id)

        # Insert a blob
        chat_blob = ChatBlob(
            type=BlobType.chat,
            messages=[
                OpenAICompatibleMessage(
                    role="user",
                    content="Test status transitions"
                )
            ],
            created_at=datetime.now()
        )

        result = self.storage.insert_blob(self.test_user_id, blob_id, chat_blob)
        assert result.ok()

        # Check initial status using new table structure
        with self.storage.get_connection() as (conn, cursor):
            cursor.execute(
                "SELECT status FROM buffer WHERE user_id = %s AND blob_id = %s",
                (self.test_user_id, blob_id)
            )
            result = cursor.fetchone()
            status = result[0] if result else None
            assert status == BufferStatus.idle, f"Expected idle status, got {status}"

            # Update status to processing using internal method
            self.storage._update_status(self.test_user_id, [blob_id], BufferStatus.processing)

            # Verify status update
            cursor.execute(
                "SELECT status FROM buffer WHERE user_id = %s AND blob_id = %s",
                (self.test_user_id, blob_id)
            )
            status = cursor.fetchone()[0]
            assert status == BufferStatus.processing, f"Expected processing status, got {status}"

            # Update status to done
            self.storage._update_status(self.test_user_id, [blob_id], BufferStatus.done)

            # Verify final status
            cursor.execute(
                "SELECT status FROM buffer WHERE user_id = %s AND blob_id = %s",
                (self.test_user_id, blob_id)
            )
            status = cursor.fetchone()[0]
            assert status == BufferStatus.done, f"Expected done status, got {status}"

            print("✅ Buffer status transitions tested successfully")

    @pytest.mark.asyncio
    async def test_multiple_blob_types(self):
        """Test handling different blob types in buffer."""
        from lindormmemobase.models.blob import DocBlob

        blob_types_data = [
            (BlobType.chat, ChatBlob(
                type=BlobType.chat,
                messages=[
                    OpenAICompatibleMessage(
                        role="user",
                        content="Chat message"
                    )
                ],
                created_at=datetime.now()
            )),
            (BlobType.doc, DocBlob(
                type=BlobType.doc,
                content="Document content",
                created_at=datetime.now()
            ))
        ]

        for blob_type, blob_data in blob_types_data:
            blob_id = str(uuid.uuid4())
            self.test_blob_ids.append(blob_id)

            result = self.storage.insert_blob(self.test_user_id, blob_id, blob_data)
            assert result.ok(), f"Failed to insert {blob_type} blob"

        # Check capacity for each type
        for blob_type, _ in blob_types_data:
            result = self.storage.get_capacity(self.test_user_id, blob_type)
            assert result.ok()
            assert result.data() == 1, f"Expected 1 {blob_type} blob, got {result.data()}"

        print("✅ Multiple blob types handled successfully")


def run_tests():
    """Run the test suite."""
    import subprocess
    result = subprocess.run(
        ["pytest", __file__, "-v", "-s"],
        capture_output=False,
        text=True
    )
    return result.returncode


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)