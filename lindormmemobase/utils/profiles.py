from ..models.profile_topic import ProfileConfig, UserProfileTopic


def read_out_profile_config(config: ProfileConfig, default_profiles: list):
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
    return default_profiles