import yaml
from pydantic import BaseModel, field_validator
from dataclasses import dataclass, field
from typing import Optional, Literal
from ..utils.text_utils import attribute_unify


@dataclass
class ProfileConfig:
    language: Literal["en", "zh"] = None
    profile_strict_mode: bool | None = None
    profile_validate_mode: bool | None = None
    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = None

    event_tags: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.language not in ["en", "zh"]:
            self.language = None
        if self.additional_user_profiles:
            [UserProfileTopic(**up) for up in self.additional_user_profiles]
        if self.overwrite_user_profiles:
            [UserProfileTopic(**up) for up in self.overwrite_user_profiles]

    @classmethod
    def load_config_string(cls, config_string: str) -> "ProfileConfig":
        overwrite_config = yaml.safe_load(config_string)
        if overwrite_config is None:
            return cls()
        # Get all field names from the dataclass
        fields = {field.name for field in dataclasses.fields(cls)}
        # Filter out any keys from overwrite_config that aren't in the dataclass
        filtered_config = {k: v for k, v in overwrite_config.items() if k in fields}
        overwrite_config = cls(**filtered_config)
        return overwrite_config


class SubTopic(BaseModel):
    name: str
    description: Optional[str] = None
    update_description: Optional[str] = None
    validate_value: Optional[bool] = None

    @field_validator("name")
    def validate_name(cls, v):
        return attribute_unify(v)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass
class EventTag:
    name: str
    description: Optional[str] = None

    def __post_init__(self):
        self.name = attribute_unify(self.name)
        self.description = self.description or ""


@dataclass
class UserProfileTopic:
    topic: str
    description: Optional[str] = None
    sub_topics: list[SubTopic] = field(default_factory=list)

    def __post_init__(self):
        self.topic = attribute_unify(self.topic)
        self.sub_topics = [
            SubTopic(**{"name": st}) if isinstance(st, str) else SubTopic(**st)
            for st in self.sub_topics
        ]


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