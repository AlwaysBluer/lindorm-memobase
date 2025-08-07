import yaml

from ....models.profile_topic import UserProfileTopic, ProfileConfig
from ....models.profile_topic import UserProfileTopic, EventTag


def formate_profile_topic(topic: UserProfileTopic) -> str:
    if not topic.sub_topics:
        return f"topic: {topic.topic}"
    return (f"topic: {topic.topic} ({topic.description or ''})\n" +
            "  subtopics:\n" +
            "\n".join(
        [
            f"    - {sp.name}" + (f"({sp.description})" if sp.description else "")
            for sp in topic.sub_topics
        ]
    ))


def modify_default_user_profile(CANDIDATE_PROFILE_TOPICS, config):
    if config.overwrite_user_profiles is not None:
        CANDIDATE_PROFILE_TOPICS = [
            UserProfileTopic(
                up["topic"],
                description=up.get("description", None),
                sub_topics=up["sub_topics"],
            )
            for up in config.overwrite_user_profiles
        ]
    elif config.additional_user_profiles:
        _addon_user_profiles = [
            UserProfileTopic(
                up["topic"],
                description=up.get("description", None),
                sub_topics=up["sub_topics"],
            )
            for up in config.additional_user_profiles
        ]
        CANDIDATE_PROFILE_TOPICS.extend(_addon_user_profiles)
    return CANDIDATE_PROFILE_TOPICS


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


def get_specific_subtopics(
    topic: str, CANDIDATE_PROFILE_TOPICS: list[UserProfileTopic]
) -> list[str]:
    sps = [
        sp
        for up in CANDIDATE_PROFILE_TOPICS
        for sp in up.sub_topics
        if up.topic == topic
    ]
    if not len(sps):
        return "None"
    return [
        f"  - {sp['name']}"
        + (f"({sp['description']})" if sp.get("description") else "")
        for sp in sps
    ]


def export_user_profile_to_yaml(profiles: list[UserProfileTopic]):
    final_results = {"profiles": []}
    for p in profiles:
        res = {"topic": p.topic}
        if p.description:
            res["description"] = p.description
        res["sub_topics"] = []
        for sp in p.sub_topics:
            res["sub_topics"].append(
                {"name": sp["name"], "description": sp["description"]}
            )
        final_results["profiles"].append(res)
    print(final_results)
    return yaml.dump(final_results, allow_unicode=True)


def init_event_tags(event_tags: list[dict]) -> list[EventTag]:
    event_tags = [
        et if isinstance(et, dict) else {"name": et, "description": None}
        for et in event_tags
    ]
    return [EventTag(et["name"], et.get("description", None)) for et in event_tags]


def read_out_event_tags(profile_config: ProfileConfig, config=None) -> list[EventTag]:
    if profile_config.event_tags is None:
        # Fallback to empty list if no config provided (to avoid dependency)
        default_event_tags = config.event_tags if config else []
        return init_event_tags(default_event_tags)
    return init_event_tags(profile_config.event_tags)
