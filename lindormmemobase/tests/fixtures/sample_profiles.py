"""
Sample user profile data for testing.

Provides realistic profile structures matching the UserProfilesV2 schema.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any


def create_sample_profile_data(user_id: str = "test_user", project_id: str = "test_project") -> List[Dict[str, Any]]:
    """Create sample profile data for testing."""
    now = datetime.now()
    
    return [
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_001",
            "content": "User is planning a trip to Japan in spring (March/April). Interested in visiting Tokyo, Kyoto, and Osaka.",
            "attributes": {
                "topic": "travel",
                "sub_topic": "destinations"
            },
            "created_at": now - timedelta(days=5),
            "updated_at": now - timedelta(days=1),
            "update_hits": 2
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_002",
            "content": "User loves Japanese food, especially ramen, sushi, and wants to try authentic kaiseki.",
            "attributes": {
                "topic": "food",
                "sub_topic": "preferences"
            },
            "created_at": now - timedelta(days=5),
            "updated_at": now - timedelta(days=1),
            "update_hits": 1
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_003",
            "content": "User prefers working in the mornings (8 AM - noon) and is most productive during this time.",
            "attributes": {
                "topic": "work",
                "sub_topic": "productivity"
            },
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=3),
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_004",
            "content": "User has a morning routine: coffee, 30-minute workout, then deep work.",
            "attributes": {
                "topic": "work",
                "sub_topic": "routine"
            },
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=3),
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_005",
            "content": "User enjoys landscape and street photography, uses Canon R5 camera.",
            "attributes": {
                "topic": "hobbies",
                "sub_topic": "photography"
            },
            "created_at": now - timedelta(days=2),
            "updated_at": now - timedelta(days=2),
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_006",
            "content": "User uses Lightroom and Photoshop for photo post-processing.",
            "attributes": {
                "topic": "hobbies",
                "sub_topic": "photography"
            },
            "created_at": now - timedelta(days=2),
            "updated_at": now - timedelta(days=2),
            "update_hits": 0
        },
    ]


def create_multilingual_profile_data(user_id: str = "test_user", project_id: str = "test_project") -> List[Dict[str, Any]]:
    """Create multilingual profile data for testing."""
    now = datetime.now()
    
    return [
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_zh_001",
            "content": "用户能流利地说英语和中文。",
            "attributes": {
                "topic": "language",
                "sub_topic": "skills"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_zh_002",
            "content": "用户在北京生活了3年学习中文。",
            "attributes": {
                "topic": "language",
                "sub_topic": "learning"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
    ]


def create_technical_profile_data(user_id: str = "test_user", project_id: str = "test_project") -> List[Dict[str, Any]]:
    """Create technical skills profile data for testing."""
    now = datetime.now()
    
    return [
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_tech_001",
            "content": "User is expert in Python programming with 10+ years experience.",
            "attributes": {
                "topic": "skills",
                "sub_topic": "programming"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_tech_002",
            "content": "User is proficient in machine learning and data science.",
            "attributes": {
                "topic": "skills",
                "sub_topic": "ai"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": project_id,
            "profile_id": "profile_tech_003",
            "content": "User has experience with AWS, Azure, and GCP cloud platforms.",
            "attributes": {
                "topic": "skills",
                "sub_topic": "cloud"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
    ]


# Profile data for different projects (multi-tenancy testing)
def create_multi_project_profile_data(user_id: str = "test_user") -> List[Dict[str, Any]]:
    """Create profile data across multiple projects."""
    now = datetime.now()
    
    return [
        {
            "user_id": user_id,
            "project_id": "project_a",
            "profile_id": "profile_a_001",
            "content": "User prefers React for frontend development in Project A.",
            "attributes": {
                "topic": "preferences",
                "sub_topic": "frontend"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": "project_b",
            "profile_id": "profile_b_001",
            "content": "User prefers Vue.js for frontend development in Project B.",
            "attributes": {
                "topic": "preferences",
                "sub_topic": "frontend"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
        {
            "user_id": user_id,
            "project_id": "project_a",
            "profile_id": "profile_a_002",
            "content": "User uses TypeScript exclusively in Project A.",
            "attributes": {
                "topic": "preferences",
                "sub_topic": "language"
            },
            "created_at": now,
            "updated_at": now,
            "update_hits": 0
        },
    ]
