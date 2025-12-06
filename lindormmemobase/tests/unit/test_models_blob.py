"""
Unit tests for blob models (models/blob.py).

Tests validation, serialization, and conversion of blob types.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from lindormmemobase.models.blob import (
    OpenAICompatibleMessage,
    BlobType,
    Blob,
    ChatBlob,
    DocBlob,
    CodeBlob,
    ImageBlob,
    TranscriptBlob,
    BlobData,
    TranscriptStamp
)


# ==================== OpenAICompatibleMessage Tests ====================

@pytest.mark.unit
class TestOpenAICompatibleMessage:
    """Test OpenAICompatibleMessage model."""
    
    def test_create_valid_user_message(self):
        """Test creating a valid user message."""
        msg = OpenAICompatibleMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.alias is None
        assert msg.created_at is None
    
    def test_create_valid_assistant_message(self):
        """Test creating a valid assistant message."""
        msg = OpenAICompatibleMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
    
    def test_create_message_with_alias(self):
        """Test creating a message with alias."""
        msg = OpenAICompatibleMessage(
            role="user",
            content="Hello",
            alias="John"
        )
        assert msg.alias == "John"
    
    def test_create_message_with_timestamp(self):
        """Test creating a message with timestamp."""
        timestamp = "2024-12-01T10:00:00"
        msg = OpenAICompatibleMessage(
            role="user",
            content="Hello",
            created_at=timestamp
        )
        assert msg.created_at == timestamp
    
    def test_invalid_role_rejected(self):
        """Test that invalid roles are rejected."""
        with pytest.raises(ValidationError):
            OpenAICompatibleMessage(role="system", content="Hello")
    
    def test_missing_content_rejected(self):
        """Test that missing content is rejected."""
        with pytest.raises(ValidationError):
            OpenAICompatibleMessage(role="user")


# ==================== BlobType Tests ====================

@pytest.mark.unit
class TestBlobType:
    """Test BlobType enum."""
    
    def test_blob_types_exist(self):
        """Test that all expected blob types exist."""
        assert BlobType.chat == "chat"
        assert BlobType.doc == "doc"
        assert BlobType.image == "image"
        assert BlobType.code == "code"
        assert BlobType.transcript == "transcript"
    
    def test_blob_type_comparison(self):
        """Test blob type string comparison."""
        assert BlobType.chat == "chat"
        assert BlobType.chat != "doc"


# ==================== ChatBlob Tests ====================

@pytest.mark.unit
class TestChatBlob:
    """Test ChatBlob model."""
    
    def test_create_simple_chat_blob(self):
        """Test creating a simple chat blob."""
        messages = [
            OpenAICompatibleMessage(role="user", content="Hello"),
            OpenAICompatibleMessage(role="assistant", content="Hi"),
        ]
        blob = ChatBlob(messages=messages)
        
        assert blob.type == BlobType.chat
        assert len(blob.messages) == 2
        assert blob.messages[0].content == "Hello"
    
    def test_chat_blob_with_timestamp(self):
        """Test chat blob with creation timestamp."""
        now = datetime.now()
        messages = [OpenAICompatibleMessage(role="user", content="Test")]
        blob = ChatBlob(messages=messages, created_at=now)
        
        assert blob.created_at == now
    
    def test_chat_blob_with_fields(self):
        """Test chat blob with custom fields."""
        messages = [OpenAICompatibleMessage(role="user", content="Test")]
        fields = {"session_id": "123", "language": "en"}
        blob = ChatBlob(messages=messages, fields=fields)
        
        assert blob.fields == fields
    
    def test_chat_blob_get_blob_data(self):
        """Test extracting blob data."""
        messages = [OpenAICompatibleMessage(role="user", content="Test")]
        blob = ChatBlob(messages=messages)
        
        blob_data = blob.get_blob_data()
        assert "messages" in blob_data
        assert "type" not in blob_data
        assert "fields" not in blob_data
    
    def test_chat_blob_to_request(self):
        """Test converting chat blob to request format."""
        messages = [OpenAICompatibleMessage(role="user", content="Test")]
        blob = ChatBlob(messages=messages)
        
        request = blob.to_request()
        assert request["blob_type"] == BlobType.chat
        assert "blob_data" in request
        assert "messages" in request["blob_data"]
    
    def test_empty_messages_allowed(self):
        """Test that empty message list is allowed."""
        blob = ChatBlob(messages=[])
        assert len(blob.messages) == 0


# ==================== DocBlob Tests ====================

@pytest.mark.unit
class TestDocBlob:
    """Test DocBlob model."""
    
    def test_create_doc_blob(self):
        """Test creating a document blob."""
        blob = DocBlob(content="This is a document.")
        
        assert blob.type == BlobType.doc
        assert blob.content == "This is a document."
    
    def test_doc_blob_with_timestamp(self):
        """Test doc blob with timestamp."""
        now = datetime.now()
        blob = DocBlob(content="Document", created_at=now)
        
        assert blob.created_at == now
    
    def test_doc_blob_get_blob_data(self):
        """Test extracting doc blob data."""
        blob = DocBlob(content="Test content")
        
        blob_data = blob.get_blob_data()
        assert blob_data["content"] == "Test content"
        assert "type" not in blob_data
    
    def test_empty_content_allowed(self):
        """Test that empty content is allowed."""
        blob = DocBlob(content="")
        assert blob.content == ""


# ==================== CodeBlob Tests ====================

@pytest.mark.unit
class TestCodeBlob:
    """Test CodeBlob model."""
    
    def test_create_code_blob(self):
        """Test creating a code blob."""
        blob = CodeBlob(content="def hello(): pass", language="python")
        
        assert blob.type == BlobType.code
        assert blob.content == "def hello(): pass"
        assert blob.language == "python"
    
    def test_code_blob_without_language(self):
        """Test code blob without language specification."""
        blob = CodeBlob(content="console.log('hello');")
        
        assert blob.language is None
    
    def test_code_blob_get_blob_data(self):
        """Test extracting code blob data."""
        blob = CodeBlob(content="code", language="js")
        
        blob_data = blob.get_blob_data()
        assert blob_data["content"] == "code"
        assert blob_data["language"] == "js"


# ==================== ImageBlob Tests ====================

@pytest.mark.unit
class TestImageBlob:
    """Test ImageBlob model."""
    
    def test_create_image_blob_with_url(self):
        """Test creating image blob with URL."""
        blob = ImageBlob(url="https://example.com/image.jpg")
        
        assert blob.type == BlobType.image
        assert blob.url == "https://example.com/image.jpg"
        assert blob.base64 is None
    
    def test_create_image_blob_with_base64(self):
        """Test creating image blob with base64."""
        blob = ImageBlob(base64="iVBORw0KGgoAAAANS...")
        
        assert blob.base64 == "iVBORw0KGgoAAAANS..."
        assert blob.url is None
    
    def test_create_image_blob_with_both(self):
        """Test creating image blob with both URL and base64."""
        blob = ImageBlob(
            url="https://example.com/image.jpg",
            base64="base64data"
        )
        
        assert blob.url is not None
        assert blob.base64 is not None


# ==================== TranscriptBlob Tests ====================

@pytest.mark.unit
class TestTranscriptBlob:
    """Test TranscriptBlob model."""
    
    def test_create_transcript_stamp(self):
        """Test creating a transcript stamp."""
        stamp = TranscriptStamp(
            content="Hello world",
            start_timestamp_in_seconds=0.0,
            end_time_timestamp_in_seconds=2.5,
            speaker="John"
        )
        
        assert stamp.content == "Hello world"
        assert stamp.start_timestamp_in_seconds == 0.0
        assert stamp.end_time_timestamp_in_seconds == 2.5
        assert stamp.speaker == "John"
    
    def test_create_transcript_blob(self):
        """Test creating a transcript blob."""
        stamps = [
            TranscriptStamp(content="Hello", start_timestamp_in_seconds=0.0),
            TranscriptStamp(content="World", start_timestamp_in_seconds=2.0)
        ]
        blob = TranscriptBlob(transcripts=stamps)
        
        assert blob.type == BlobType.transcript
        assert len(blob.transcripts) == 2


# ==================== BlobData Tests ====================

@pytest.mark.unit
class TestBlobData:
    """Test BlobData model and conversion."""
    
    def test_create_blob_data(self):
        """Test creating BlobData instance."""
        blob_data = BlobData(
            blob_type=BlobType.chat,
            blob_data={
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            }
        )
        
        assert blob_data.blob_type == BlobType.chat
        assert "messages" in blob_data.blob_data
    
    def test_blob_data_to_chat_blob(self):
        """Test converting BlobData to ChatBlob."""
        blob_data = BlobData(
            blob_type=BlobType.chat,
            blob_data={
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"}
                ]
            }
        )
        
        blob = blob_data.to_blob()
        
        assert isinstance(blob, ChatBlob)
        assert len(blob.messages) == 2
        assert blob.messages[0].content == "Hello"
    
    def test_blob_data_to_doc_blob(self):
        """Test converting BlobData to DocBlob."""
        blob_data = BlobData(
            blob_type=BlobType.doc,
            blob_data={"content": "Document text"}
        )
        
        blob = blob_data.to_blob()
        
        assert isinstance(blob, DocBlob)
        assert blob.content == "Document text"
    
    def test_blob_data_with_fields(self):
        """Test BlobData with custom fields."""
        now = datetime.now()
        blob_data = BlobData(
            blob_type=BlobType.chat,
            blob_data={"messages": []},
            fields={"custom": "value"},
            created_at=now
        )
        
        blob = blob_data.to_blob()
        assert blob.fields == {"custom": "value"}
        assert blob.created_at == now
    
    def test_image_blob_not_implemented(self):
        """Test that ImageBlob conversion raises NotImplementedError."""
        blob_data = BlobData(
            blob_type=BlobType.image,
            blob_data={"url": "http://example.com/img.jpg"}
        )
        
        with pytest.raises(NotImplementedError):
            blob_data.to_blob()
    
    def test_transcript_blob_not_implemented(self):
        """Test that TranscriptBlob conversion raises NotImplementedError."""
        blob_data = BlobData(
            blob_type=BlobType.transcript,
            blob_data={"transcripts": []}
        )
        
        with pytest.raises(NotImplementedError):
            blob_data.to_blob()
