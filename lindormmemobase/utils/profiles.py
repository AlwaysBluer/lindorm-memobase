from ..models.profile_topic import ProfileConfig, UserProfileTopic


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