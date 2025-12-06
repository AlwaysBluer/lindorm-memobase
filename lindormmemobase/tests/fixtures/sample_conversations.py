"""
Sample conversation data for testing.

Provides realistic OpenAI-compatible message sequences.
"""

from lindormmemobase.models.blob import OpenAICompatibleMessage
from typing import List


def create_simple_conversation() -> List[OpenAICompatibleMessage]:
    """Create a simple two-turn conversation."""
    return [
        OpenAICompatibleMessage(role="user", content="Hello!"),
        OpenAICompatibleMessage(role="assistant", content="Hi! How can I help you today?"),
    ]


def create_travel_conversation() -> List[OpenAICompatibleMessage]:
    """Create a conversation about travel planning."""
    return [
        OpenAICompatibleMessage(
            role="user",
            content="I'm planning a trip to Japan and need some advice."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="I'd be happy to help! When are you planning to visit and what are your interests?"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="I want to go in spring, around March. I love food and photography."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="Perfect! Spring is cherry blossom season. For food and photography, I recommend Tokyo, Kyoto, and Osaka."
        ),
    ]


def create_technical_conversation() -> List[OpenAICompatibleMessage]:
    """Create a technical discussion conversation."""
    return [
        OpenAICompatibleMessage(
            role="user",
            content="I need help with async programming in Python."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="I can help with that! What specific aspect of async programming are you working on?"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="I'm trying to understand when to use asyncio vs threading."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="Great question! Use asyncio for I/O-bound tasks and threading for CPU-bound tasks. Asyncio is more efficient for I/O operations."
        ),
        OpenAICompatibleMessage(
            role="user",
            content="That makes sense. I'm working with HTTP requests, so asyncio seems better."
        ),
    ]


def create_preferences_conversation() -> List[OpenAICompatibleMessage]:
    """Create a conversation expressing user preferences."""
    return [
        OpenAICompatibleMessage(
            role="user",
            content="I prefer working early in the morning when it's quiet."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="That's a good strategy! Many people find they're most productive in the morning."
        ),
        OpenAICompatibleMessage(
            role="user",
            content="Yes, I usually start at 6 AM with coffee and light exercise."
        ),
    ]


def create_mixed_topic_conversation() -> List[OpenAICompatibleMessage]:
    """Create a conversation covering multiple topics."""
    return [
        OpenAICompatibleMessage(
            role="user",
            content="I've been learning photography lately."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="That's wonderful! What type of photography interests you?"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="Mainly landscape, but I also enjoy street photography."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="Both are great! Do you have a camera you use?"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="I use a Canon R5. By the way, I also love cooking Japanese food."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="Nice camera! And Japanese cuisine is delicious. What dishes do you like to make?"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="I make ramen from scratch and various sushi rolls."
        ),
    ]


def create_long_context_conversation() -> List[OpenAICompatibleMessage]:
    """Create a longer conversation for context testing."""
    messages = []
    
    # Opening
    messages.extend([
        OpenAICompatibleMessage(
            role="user",
            content="I need help planning my career development."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="I'd be glad to help! What's your current role and what are your goals?"
        ),
    ])
    
    # Background discussion
    messages.extend([
        OpenAICompatibleMessage(
            role="user",
            content="I'm a software engineer with 5 years of experience in backend development."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="That's a solid foundation. What technologies do you work with?"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="Mainly Python and Go, with PostgreSQL and Redis for data storage."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="Excellent stack! Where do you want to grow - technically or towards leadership?"
        ),
    ])
    
    # Goals discussion
    messages.extend([
        OpenAICompatibleMessage(
            role="user",
            content="I'm interested in both. I want to become a tech lead eventually."
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="Great goal! That typically requires strong technical skills plus leadership abilities."
        ),
        OpenAICompatibleMessage(
            role="user",
            content="What skills should I focus on developing?"
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="System design, mentoring, project management, and communication are key for tech leads."
        ),
    ])
    
    return messages


def create_chinese_conversation() -> List[OpenAICompatibleMessage]:
    """Create a conversation in Chinese."""
    return [
        OpenAICompatibleMessage(
            role="user",
            content="你好！我想学习中文。"
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="你好！学习中文是一个很好的决定。你现在的中文水平怎么样？"
        ),
        OpenAICompatibleMessage(
            role="user",
            content="我是初学者，刚开始学习。"
        ),
        OpenAICompatibleMessage(
            role="assistant",
            content="没问题！我建议你从拼音和基础汉字开始学习。"
        ),
    ]


# Preset conversation collections
SAMPLE_CONVERSATIONS = {
    "simple": create_simple_conversation(),
    "travel": create_travel_conversation(),
    "technical": create_technical_conversation(),
    "preferences": create_preferences_conversation(),
    "mixed": create_mixed_topic_conversation(),
    "long": create_long_context_conversation(),
    "chinese": create_chinese_conversation(),
}
