import yaml
import dataclasses
import re
from pydantic import BaseModel, field_validator
from dataclasses import dataclass, field
from typing import Optional, Literal
from lindormmemobase.utils.text_utils import attribute_unify


@dataclass
class ProfileConfig:
    language: Literal["en", "zh"] = None
    profile_strict_mode: bool | None = None
    profile_validate_mode: bool | None = None
    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = None
    event_tags: Optional[list[dict]] = None

    # Merge configuration fields (T005-T006)
    merge_thresholds: dict[str, int] = field(default_factory=dict)
    max_pending_profiles: int = 1000

    def __post_init__(self):
        if self.language not in ["en", "zh"]:
            self.language = None
        if self.additional_user_profiles:
            [UserProfileTopic(**up) for up in self.additional_user_profiles]
        if self.overwrite_user_profiles:
            [UserProfileTopic(**up) for up in self.overwrite_user_profiles]

        # T008: Validate merge_thresholds format
        if self.merge_thresholds:
            pattern = re.compile(r"^[a-z_]+::[a-z_]+$")
            for key, value in self.merge_thresholds.items():
                if not pattern.match(key):
                    raise ValueError(
                        f"Invalid merge_thresholds key format: '{key}'. "
                        "Must match pattern 'topic::subtopic' with lowercase letters and underscores only."
                    )
                if not isinstance(value, int) or value < 1:
                    raise ValueError(
                        f"Invalid merge_thresholds value for '{key}': {value}. "
                        "Threshold must be an integer >= 1."
                    )

        # T008: Validate max_pending_profiles
        if not isinstance(self.max_pending_profiles, int) or self.max_pending_profiles < 1:
            raise ValueError(
                f"Invalid max_pending_profiles: {self.max_pending_profiles}. "
                "Must be an integer >= 1."
            )

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
    
    @classmethod
    def load_from_file(cls, config_file_path: str) -> "ProfileConfig":
        """Load ProfileConfig from YAML file."""
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
            return cls.load_config_string(config_content)
        except FileNotFoundError:
            return cls()  # Return default config if file not found
        except Exception as e:
            raise ValueError(f"Failed to load ProfileConfig from {config_file_path}: {e}")
    
    @classmethod
    def load_from_config(cls, main_config) -> "ProfileConfig":
        """Create ProfileConfig from main Config object, extracting relevant fields."""
        profile_fields = {
            'language': main_config.language,
            'profile_strict_mode': main_config.profile_strict_mode,
            'profile_validate_mode': main_config.profile_validate_mode,
            'additional_user_profiles': main_config.additional_user_profiles,
            'overwrite_user_profiles': main_config.overwrite_user_profiles,
            'event_theme_requirement': main_config.event_theme_requirement,
            'event_tags': main_config.event_tags,
            'merge_thresholds': main_config.merge_thresholds,
            'max_pending_profiles': main_config.max_pending_profiles
        }
        return cls(**profile_fields)

    def _to_yaml_string(self) -> str:
        """
        Convert ProfileConfig to YAML string.

        Returns:
            YAML representation of this config
        """
        # Convert dataclass to dict, excluding None values
        fields_dict = dataclasses.asdict(self)
        # Filter out None values
        filtered_dict = {k: v for k, v in fields_dict.items() if v is not None}
        return yaml.dump(filtered_dict, allow_unicode=True, default_flow_style=False)


class SubTopic(BaseModel):
    name: str
    description: Optional[str] = None
    update_description: Optional[str] = None
    validate_value: Optional[bool] = None
    merge_threshold: Optional[int] = None  # T007: Subtopic-level merge threshold

    @field_validator("name")
    def validate_name(cls, v):
        return attribute_unify(v)

    @field_validator("merge_threshold")
    def validate_merge_threshold(cls, v):
        if v is not None and v < 1:
            raise ValueError(f"merge_threshold must be >= 1, got {v}")
        return v

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