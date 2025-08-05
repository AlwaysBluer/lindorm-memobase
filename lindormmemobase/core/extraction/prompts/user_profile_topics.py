from config import LOG
from .profile_init_utils import (
    UserProfileTopic,
    formate_profile_topic,
    modify_default_user_profile,
)


# Base profile topics without config modification
BASE_CANDIDATE_PROFILE_TOPICS: list[UserProfileTopic] = [
    UserProfileTopic(
        "basic_info",
        sub_topics=[
            "Name",
            {
                "name": "Age",
                "description": "integer",
            },
            "Gender",
            "birth_date",
            "nationality",
            "ethnicity",
            "language_spoken",
        ],
    ),
    UserProfileTopic(
        "contact_info",
        sub_topics=[
            "email",
            "phone",
            "city",
            "country",
        ],
    ),
    UserProfileTopic(
        "education",
        sub_topics=[
            "school",
            "degree",
            "major",
        ],
    ),
    UserProfileTopic(
        "demographics",
        sub_topics=[
            "marital_status",
            "number_of_children",
            "household_income",
        ],
    ),
    UserProfileTopic(
        "work",
        sub_topics=[
            "company",
            "title",
            "working_industry",
            "previous_projects",
            "work_skills",
        ],
    ),
    UserProfileTopic(
        "interest",
        sub_topics=[
            "books",
            "movies",
            "music",
            "foods",
            "sports",
        ],
    ),
    UserProfileTopic(
        "psychological",
        sub_topics=["personality", "values", "beliefs", "motivations", "goals"],
    ),
    UserProfileTopic(
        "life_event",
        sub_topics=["marriage", "relocation", "retirement"],
    ),
]


def get_candidate_profile_topics(config=None) -> list[UserProfileTopic]:
    """Get profile topics, optionally modified by user config"""
    if config is None:
        return BASE_CANDIDATE_PROFILE_TOPICS.copy()
    return modify_default_user_profile(BASE_CANDIDATE_PROFILE_TOPICS.copy(), config)

# Backward compatibility - use base topics without config
CANDIDATE_PROFILE_TOPICS = BASE_CANDIDATE_PROFILE_TOPICS


def get_prompt(profiles: list[UserProfileTopic] = None):
    if profiles is None:
        profiles = BASE_CANDIDATE_PROFILE_TOPICS
    return "\n".join([formate_profile_topic(up) for up in profiles]) + "\n..."


# Remove module-level CONFIG usage - users need to call this explicitly
# if CONFIG.language == "en":
#     LOG.info(f"User profiles: \n{get_prompt()}")

if __name__ == "__main__":
    print(get_prompt())
