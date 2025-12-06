"""
Sample blob data for testing.

Provides realistic ChatBlob and DocBlob instances for use in tests.
"""

from datetime import datetime
from lindormmemobase.models.blob import (
    ChatBlob,
    DocBlob,
    CodeBlob,
    BlobType,
    OpenAICompatibleMessage
)


def create_simple_chat_blob() -> ChatBlob:
    """Create a simple chat blob with basic conversation."""
    return ChatBlob(
        messages=[
            OpenAICompatibleMessage(role="user", content="Hi there!"),
            OpenAICompatibleMessage(role="assistant", content="Hello! How can I help you today?"),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )


def create_travel_chat_blob() -> ChatBlob:
    """Create a chat blob about travel planning."""
    return ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="I'm planning a trip to Japan next spring."
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="That's wonderful! Japan in spring is beautiful, especially during cherry blossom season. Where are you thinking of visiting?"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="I want to visit Tokyo, Kyoto, and Osaka. I love Japanese food and culture."
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="Great choices! Those cities offer amazing food experiences. Are you interested in any specific cuisines like ramen, sushi, or kaiseki?"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="I'm really into ramen and sushi. Also want to try authentic kaiseki."
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )


def create_preferences_chat_blob() -> ChatBlob:
    """Create a chat blob expressing user preferences."""
    return ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="I prefer working in the mornings. I'm most productive between 8 AM and noon."
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="That's great to know! Morning productivity is quite common. Do you have any specific routines?"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="Yes, I usually start with coffee and a 30-minute workout, then dive into deep work."
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )


def create_hobby_chat_blob() -> ChatBlob:
    """Create a chat blob about hobbies and interests."""
    return ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="I've been really into photography lately."
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="That's a wonderful hobby! What type of photography interests you most?"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="Mainly landscape and street photography. I use a Canon R5."
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="Excellent choice of camera! Do you do any post-processing?"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="Yes, I use Lightroom and occasionally Photoshop for more complex edits."
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )


def create_multilingual_chat_blob() -> ChatBlob:
    """Create a chat blob with mixed language content."""
    return ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="I can speak English and Chinese fluently. 我也会说中文。"
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="That's impressive! Being bilingual is a valuable skill. How did you learn both languages?"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="English is my native language, and I learned Chinese while living in Beijing for 3 years."
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )


def create_doc_blob_about_preferences() -> DocBlob:
    """Create a document blob describing user preferences."""
    return DocBlob(
        content="""
        User Preferences Summary:
        - Prefers asynchronous communication over real-time meetings
        - Works best in quiet environments with minimal distractions
        - Enjoys collaborative projects but needs focused individual time
        - Values work-life balance and flexible schedules
        - Interested in continuous learning and professional development
        """,
        type=BlobType.doc,
        created_at=datetime.now()
    )


def create_doc_blob_about_skills() -> DocBlob:
    """Create a document blob about user skills."""
    return DocBlob(
        content="""
        Technical Skills:
        - Expert in Python programming (10+ years experience)
        - Proficient in machine learning and data science
        - Experienced with cloud platforms (AWS, Azure, GCP)
        - Strong background in database design and optimization
        - Familiar with DevOps practices and CI/CD pipelines
        
        Soft Skills:
        - Excellent written and verbal communication
        - Strong problem-solving abilities
        - Team leadership and mentoring experience
        - Adaptable to changing requirements
        """,
        type=BlobType.doc,
        created_at=datetime.now()
    )


def create_code_blob_python() -> CodeBlob:
    """Create a code blob with Python code."""
    return CodeBlob(
        content="""
def fibonacci(n: int) -> int:
    '''Calculate the nth Fibonacci number using recursion.'''
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# User's preferred coding style: type hints, docstrings, clear naming
        """,
        language="python",
        type=BlobType.code,
        created_at=datetime.now()
    )


def create_long_conversation_blob() -> ChatBlob:
    """Create a longer conversation blob for token testing."""
    messages = []
    for i in range(20):
        messages.extend([
            OpenAICompatibleMessage(
                role="user",
                content=f"This is message {i*2+1} in a longer conversation. "
                        f"It contains information about user preferences and behaviors."
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content=f"This is response {i*2+2}. I acknowledge your input and provide relevant information."
            ),
        ])
    
    return ChatBlob(
        messages=messages,
        type=BlobType.chat,
        created_at=datetime.now()
    )


# Collection of sample blobs for batch testing
SAMPLE_CHAT_BLOBS = [
    create_simple_chat_blob(),
    create_travel_chat_blob(),
    create_preferences_chat_blob(),
    create_hobby_chat_blob(),
]

SAMPLE_DOC_BLOBS = [
    create_doc_blob_about_preferences(),
    create_doc_blob_about_skills(),
]
