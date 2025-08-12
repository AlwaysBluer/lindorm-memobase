#!/usr/bin/env python3
"""
Buffer Storage Integration Tests

This test suite tests the LindormBufferStorage implementation
using real Lindorm Wide Table connections from .env configuration.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
import asyncio
import json
import pytest
import uuid
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from lindormmemobase.config import Config
from lindormmemobase.core.constants import BufferStatus
from lindormmemobase.core.buffer.buffer import (
    LindormBufferStorage,
)
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage


# Load .env file from the tests directory
test_dir = Path(__file__).parent
env_file = test_dir / ".env"
load_dotenv(env_file)

class TestBufferStorage:
    """Test suite for LindormBufferStorage using real Lindorm connections."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        cls.config = Config.load_config()

        cls.storage = LindormBufferStorage(cls.config)
        cls.test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        cls.test_blob_ids = []
        cls.test_buffer_ids = []
    
    @classmethod
    def teardown_class(cls):
        """Cleanup test data after all tests."""
        asyncio.run(cls._cleanup_test_data())
    
    @classmethod
    async def _cleanup_test_data(cls):
        """Clean up test data from database."""
        pool = cls.storage._get_pool()
        conn = pool.get_connection()
        cursor = None
        
        try:
            cursor = conn.cursor()
            # Delete test buffer zone entries
            cursor.execute(
                "DELETE FROM buffer_zone WHERE user_id = %s",
                (cls.test_user_id,)
            )
            
            # Delete test blob content entries
            cursor.execute(
                "DELETE FROM blob_content WHERE user_id = %s",
                (cls.test_user_id,)
            )
            
            conn.commit()
            print(f"✅ Cleaned up test data for user: {cls.test_user_id}")
            
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error cleaning up test data: {e}")
        finally:
            if cursor:
                cursor.close()
            conn.close()
    
    def setup_method(self):
        """Setup before each test method."""
        self.test_blob_ids = []
        self.test_buffer_ids = []
    
    def teardown_method(self):
        """Cleanup after each test method."""
        asyncio.run(self._cleanup_method_data())
    
    async def _cleanup_method_data(self):
        """Clean up data created by individual test methods."""
        if not self.test_buffer_ids and not self.test_blob_ids:
            return
            
        pool = self.storage._get_pool()
        conn = pool.get_connection()
        cursor = None
        
        try:
            cursor = conn.cursor()
            
            # Delete specific test buffer entries
            if self.test_buffer_ids:
                placeholders = ','.join(['%s'] * len(self.test_buffer_ids))
                cursor.execute(
                    f"DELETE FROM buffer_zone WHERE id IN ({placeholders})",
                    self.test_buffer_ids
                )
            
            # Delete specific test blob entries
            if self.test_blob_ids:
                placeholders = ','.join(['%s'] * len(self.test_blob_ids))
                cursor.execute(
                    f"DELETE FROM blob_content WHERE blob_id IN ({placeholders})",
                    self.test_blob_ids
                )
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error in method cleanup: {e}")
        finally:
            if cursor:
                cursor.close()
            conn.close()
    
    @pytest.mark.asyncio
    async def test_insert_blob_to_buffer(self):
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
        p = await self.storage.insert_blob_to_buffer(
            self.test_user_id,
            blob_id,
            chat_blob
        )
        
        assert p.ok(), f"Failed to insert blob: {p.msg()}"
        
        # Verify insertion by checking the database
        pool = self.storage._get_pool()
        conn = pool.get_connection()
        cursor = None
        
        try:
            cursor = conn.cursor()
            
            # Check buffer_zone table
            cursor.execute(
                "SELECT COUNT(*) FROM buffer_zone WHERE user_id = %s AND blob_id = %s",
                (self.test_user_id, blob_id)
            )
            count = cursor.fetchone()[0]
            assert count == 1, "Blob not found in buffer_zone"
            
            # Check blob_content table
            cursor.execute(
                "SELECT COUNT(*) FROM blob_content WHERE user_id = %s AND blob_id = %s",
                (self.test_user_id, blob_id)
            )
            count = cursor.fetchone()[0]
            assert count == 1, "Blob not found in blob_content"
            
        finally:
            if cursor:
                cursor.close()
            conn.close()
    
    @pytest.mark.asyncio
    async def test_get_buffer_capacity(self):
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
            
            p = await self.storage.insert_blob_to_buffer(
                self.test_user_id,
                blob_id,
                chat_blob
            )
            assert p.ok()
        
        # Get buffer capacity
        p = await self.storage.get_buffer_capacity(self.test_user_id, BlobType.chat)
        assert p.ok(), f"Failed to get buffer capacity: {p.msg()}"
        assert p.data() == 3, f"Expected capacity of 3, got {p.data()}"
    
    @pytest.mark.asyncio
    async def test_get_unprocessed_buffer_ids(self):
        """Test getting unprocessed buffer IDs."""
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
            
            p = await self.storage.insert_blob_to_buffer(
                self.test_user_id,
                blob_id,
                chat_blob
            )
            assert p.ok()
        
        # Get unprocessed buffer IDs
        p = await self.storage.get_unprocessed_buffer_ids(
            self.test_user_id,
            BlobType.chat,
            BufferStatus.idle
        )
        
        assert p.ok(), f"Failed to get unprocessed buffer IDs: {p.msg()}"
        buffer_ids = p.data()
        assert len(buffer_ids) == 2, f"Expected 2 unprocessed buffers, got {len(buffer_ids)}"
        
        # Store for cleanup
        self.test_buffer_ids.extend(buffer_ids)
    
    @pytest.mark.asyncio
    async def test_detect_buffer_full_or_not(self):
        """Test detecting if buffer is full based on token size."""
        # Insert blobs with large content to trigger buffer full
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
            
            p = await self.storage.insert_blob_to_buffer(
                self.test_user_id,
                blob_id,
                chat_blob
            )
            assert p.ok()
        
        # Detect if buffer is full
        p = await self.storage.detect_buffer_full_or_not(
            self.test_user_id,
            BlobType.chat,
            self.config
        )
        
        assert p.ok(), f"Failed to detect buffer full: {p.msg()}"
        buffer_ids = p.data()
        
        # Should return buffer IDs if token size exceeds limit
        # The actual result depends on config.max_chat_blob_buffer_token_size
        print(f"Buffer full detection returned {len(buffer_ids)} buffer IDs")
        
        if buffer_ids:
            self.test_buffer_ids.extend(buffer_ids)
    
    @pytest.mark.asyncio
    async def test_flush_buffer_by_ids_without_processing(self):
        """Test flush_buffer_by_ids method (without actual blob processing)."""
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
                        content=f"Message to flush {i}"
                    )
                ],
                created_at=datetime.now()
            )
            
            p = await self.storage.insert_blob_to_buffer(
                self.test_user_id,
                blob_id,
                chat_blob
            )
            assert p.ok()
        
        # Get buffer IDs
        p = await self.storage.get_unprocessed_buffer_ids(
            self.test_user_id,
            BlobType.chat,
            BufferStatus.idle
        )
        assert p.ok()
        buffer_ids = p.data()
        self.test_buffer_ids.extend(buffer_ids)
        
        # Note: Actual flush_buffer_by_ids requires process_blobs to work
        # which needs proper ProfileConfig and extraction setup
        # For basic testing, we'll verify the data retrieval part
        
        # Test the data retrieval logic (first part of flush_buffer_by_ids)
        pool = self.storage._get_pool()
        conn = pool.get_connection()
        cursor = None
        
        try:
            cursor = conn.cursor()
            
            # Test the separate query approach (no JOIN)
            # First query buffer_zone
            buffer_ids_placeholder = ','.join(['%s'] * len(buffer_ids))
            query_buffer = f"""
                SELECT 
                    id as buffer_id,
                    blob_id,
                    token_size,
                    created_at as buffer_created_at
                FROM buffer_zone
                WHERE user_id = %s 
                    AND blob_type = %s 
                    AND status = %s 
                    AND id IN ({buffer_ids_placeholder})
                ORDER BY created_at
            """
            cursor.execute(query_buffer, [self.test_user_id, str(BlobType.chat), BufferStatus.idle] + buffer_ids)
            buffer_data = cursor.fetchall()
            
            assert len(buffer_data) == 2, f"Expected 2 buffer records, got {len(buffer_data)}"
            
            # Get blob_ids and query blob_content
            retrieved_blob_ids = [row[1] for row in buffer_data]
            blob_ids_placeholder = ','.join(['%s'] * len(retrieved_blob_ids))
            
            query_blob = f"""
                SELECT 
                    blob_id,
                    blob_data,
                    created_at
                FROM blob_content
                WHERE user_id = %s 
                    AND blob_id IN ({blob_ids_placeholder})
            """
            cursor.execute(query_blob, [self.test_user_id] + retrieved_blob_ids)
            blob_content_data = cursor.fetchall()
            
            assert len(blob_content_data) == 2, f"Expected 2 blob records, got {len(blob_content_data)}"
            
            # Verify data mapping works
            blob_map = {row[0]: (row[1], row[2]) for row in blob_content_data}
            
            buffer_blob_data = []
            for buffer_row in buffer_data:
                buffer_id, blob_id, token_size, buffer_created_at = buffer_row
                assert blob_id in blob_map, f"Blob ID {blob_id} not found in blob_content"
                blob_data, created_at = blob_map[blob_id]
                buffer_blob_data.append((buffer_id, blob_id, token_size, buffer_created_at, blob_data, created_at))
            
            assert len(buffer_blob_data) == 2, "Data merge failed"
            
            print(f"✅ Successfully tested data retrieval without JOIN for {len(buffer_blob_data)} records")
            
        finally:
            if cursor:
                cursor.close()
            conn.close()
    
    @pytest.mark.asyncio
    async def test_buffer_status_updates(self):
        """Test buffer status transitions."""
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
        
        p = await self.storage.insert_blob_to_buffer(
            self.test_user_id,
            blob_id,
            chat_blob
        )
        assert p.ok()
        
        # Get the buffer ID
        pool = self.storage._get_pool()
        conn = pool.get_connection()
        cursor = None
        
        try:
            cursor = conn.cursor()
            
            # Check initial status
            cursor.execute(
                "SELECT id, status FROM buffer_zone WHERE user_id = %s AND blob_id = %s",
                (self.test_user_id, blob_id)
            )
            result = cursor.fetchone()
            buffer_id, status = result
            self.test_buffer_ids.append(buffer_id)
            
            assert status == BufferStatus.idle, f"Expected idle status, got {status}"
            
            # Update status to processing
            cursor.execute(
                "UPDATE buffer_zone SET status = %s WHERE id = %s",
                (BufferStatus.processing, buffer_id)
            )
            conn.commit()
            
            # Verify status update
            cursor.execute(
                "SELECT status FROM buffer_zone WHERE id = %s",
                (buffer_id,)
            )
            status = cursor.fetchone()[0]
            assert status == BufferStatus.processing, f"Expected processing status, got {status}"
            
            # Update status to done
            cursor.execute(
                "UPDATE buffer_zone SET status = %s WHERE id = %s",
                (BufferStatus.done, buffer_id)
            )
            conn.commit()
            
            # Verify final status
            cursor.execute(
                "SELECT status FROM buffer_zone WHERE id = %s",
                (buffer_id,)
            )
            status = cursor.fetchone()[0]
            assert status == BufferStatus.done, f"Expected done status, got {status}"
            
            print("✅ Buffer status transitions tested successfully")
            
        finally:
            if cursor:
                cursor.close()
            conn.close()
    
    @pytest.mark.asyncio
    async def test_multiple_blob_types(self):
        """Test handling different blob types in buffer."""
        from lindormmemobase.models.blob import DocBlob, CodeBlob
        
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
            )),
            (BlobType.code, CodeBlob(
                type=BlobType.code,
                language="python",
                content="print('Hello')",
                created_at=datetime.now()
            ))
        ]
        
        for blob_type, blob_data in blob_types_data:
            blob_id = str(uuid.uuid4())
            self.test_blob_ids.append(blob_id)
            
            p = await self.storage.insert_blob_to_buffer(
                self.test_user_id,
                blob_id,
                blob_data
            )
            assert p.ok(), f"Failed to insert {blob_type} blob"
        
        # Check capacity for each type
        for blob_type, _ in blob_types_data:
            p = await self.storage.get_buffer_capacity(self.test_user_id, blob_type)
            assert p.ok()
            assert p.data() == 1, f"Expected 1 {blob_type} blob, got {p.data()}"
        
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