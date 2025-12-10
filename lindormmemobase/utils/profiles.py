from typing import Optional, List
from lindormmemobase.models.types import Profile, ProfileEntry
from lindormmemobase.models.profile_topic import ProfileConfig, UserProfileTopic

def read_out_profile_config(config: ProfileConfig, default_profiles: list, main_config=None):
    # Check ProfileConfig first (highest priority)
    if config.overwrite_user_profiles:
        profile_topics = [
            UserProfileTopic(
                up["topic"],
                description=up.get("description", None),
                sub_topics=up["sub_topics"],
            )
            for up in config.overwrite_user_profiles
        ]
        return profile_topics
    elif config.additional_user_profiles:
        profile_topics = [
            UserProfileTopic(
                up["topic"],
                description=up.get("description", None),
                sub_topics=up["sub_topics"],
            )
            for up in config.additional_user_profiles
        ]
        return default_profiles + profile_topics
    
    # Fallback to main_config if ProfileConfig has no profiles (like event_tags does)
    if main_config:
        if main_config.overwrite_user_profiles:
            profile_topics = [
                UserProfileTopic(
                    up["topic"],
                    description=up.get("description", None),
                    sub_topics=up["sub_topics"],
                )
                for up in main_config.overwrite_user_profiles
            ]
            return profile_topics
        elif main_config.additional_user_profiles:
            profile_topics = [
                UserProfileTopic(
                    up["topic"],
                    description=up.get("description", None),
                    sub_topics=up["sub_topics"],
                )
                for up in main_config.additional_user_profiles
            ]
            return default_profiles + profile_topics
    
    # Final fallback to default_profiles
    return default_profiles

def convert_profile_data_to_profiles(raw_profiles, delimiter, topics: Optional[List[str]] = None, max_profiles: Optional[int] = None) -> List[Profile]:
    """Convert ProfileData list to Profile list with topic grouping.
    Concatenate all entries under each topic::subtopic into a single memo using a delimiter.
    """
    # topic_groups structure: { topic: { subtopic: ProfileEntry } }
    topic_groups: dict[str, dict[str, ProfileEntry]] = {}
    delimiter = delimiter or "; "

    profile_list = raw_profiles[:max_profiles] if max_profiles else raw_profiles

    for profile_data in profile_list:
        topic = profile_data.attributes.get("topic", "general")
        subtopic = profile_data.attributes.get("sub_topic", "general")

        if topics and topic not in topics:
            continue

        if topic not in topic_groups:
            topic_groups[topic] = {}

        ts = profile_data.updated_at.timestamp() if profile_data.updated_at else None

        existing = topic_groups[topic].get(subtopic)
        if existing is None:
            # First entry for this (topic, subtopic)
            topic_groups[topic][subtopic] = ProfileEntry(
                content=profile_data.content,
                last_updated=ts
            )
        else:
            # Append content with delimiter, preserve non-destructive history
            if profile_data.content:
                existing.content = (
                    f"{existing.content}{delimiter}{profile_data.content}"
                    if existing.content else profile_data.content
                )
            # Update last_updated to the most recent timestamp
            if ts is not None:
                if existing.last_updated is None or ts > existing.last_updated:
                    existing.last_updated = ts

    return [Profile(topic=topic, subtopics=subtopics) for topic, subtopics in topic_groups.items()]