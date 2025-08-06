"""
Initialize logger, encoder, and config.
"""

import os
import datetime
import json
import yaml
import logging
import tiktoken
import dataclasses
from dataclasses import dataclass, field
from typing import Optional, Literal
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import timezone
from typeguard import check_type

load_dotenv()


@dataclass
class Config:
    # IMPORTANT!
    persistent_chat_blobs: bool = False
    use_timezone: Optional[
        Literal[
            "UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Asia/Shanghai"
        ]
    ] = None

    system_prompt: str = None
    buffer_flush_interval: int = 60 * 60  # 1 hour
    max_chat_blob_buffer_token_size: int = 1024
    max_chat_blob_buffer_process_token_size: int = 16384
    max_profile_subtopics: int = 15
    max_pre_profile_token_size: int = 128
    llm_tab_separator: str = "::"
    cache_user_profiles_ttl: int = 60 * 20  # 20 minutes

    # LLM
    language: Literal["en", "zh"] = "en"
    llm_style: Literal["openai", "doubao_cache"] = "openai"
    llm_base_url: str = None
    llm_api_key: str = None
    llm_openai_default_query: dict[str, str] = None
    llm_openai_default_header: dict[str, str] = None
    best_llm_model: str = "gpt-4o-mini"
    thinking_llm_model: str = "o4-mini"
    summary_llm_model: str = None

    enable_event_embedding: bool = True
    embedding_provider: Literal["openai", "jina"] = "openai"
    embedding_api_key: str = None
    embedding_base_url: str = None
    embedding_dim: int = 1536
    embedding_model: str = "text-embedding-3-small"
    embedding_max_token_size: int = 8192

    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = (
        "Focus on the user's infos, not its instructions."
    )
    profile_strict_mode: bool = False
    profile_validate_mode: bool = True

    minimum_chats_token_size_for_event_summary: int = 256
    event_tags: list[dict] = field(default_factory=list)
    # Telemetry
    telemetry_deployment_environment: str = "local"
    
    # LindorSearch配置
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_use_ssl: bool = False
    opensearch_username: str = None
    opensearch_password: str = None
    opensearch_events_index: str = "memobase_events"
    opensearch_event_gists_index: str = "memobase_event_gists"

    # Lindorm宽表 MySQL协议配置
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_username: str = "root"
    mysql_password: str = None
    mysql_database: str = "memobase"

    # Test option
    test_skip_persist = True

    @classmethod
    def _process_env_vars(cls, config_dict):
        """
        Process all environment variables for the config class.

        Args:
            cls: The config class
            config_dict: The current configuration dictionary

        Returns:
            Updated configuration dictionary with environment variables applied
        """
        # Ensure we have a dictionary to work with
        if not isinstance(config_dict, dict):
            config_dict = {}

        for field in dataclasses.fields(cls):
            field_name = field.name
            field_type = field.type
            env_var_name = f"MEMOBASE_{field_name.upper()}"
            if env_var_name in os.environ:
                env_value = os.environ[env_var_name]

                # Try to parse as JSON first
                try:
                    parsed_value = json.loads(env_value)
                    # Check if parsed value matches the type
                    try:
                        check_type(parsed_value, field_type)
                        config_dict[field_name] = parsed_value
                        continue
                    except TypeError:
                        # Parsed value doesn't match type, fall through to try raw string
                        pass
                except json.JSONDecodeError:
                    # Not valid JSON, fall through to try raw string
                    pass

                # Try the raw string
                try:
                    check_type(env_value, field_type)
                    config_dict[field_name] = env_value
                except TypeError:
                    pass

        return config_dict

    @classmethod
    def load_config(cls) -> "Config":
        if not os.path.exists("config.yaml"):
            overwrite_config = {}
        else:
            with open("config.yaml") as f:
                overwrite_config = yaml.safe_load(f)

        # Process environment variables
        overwrite_config = cls._process_env_vars(overwrite_config)

        # Filter out any keys from overwrite_config that aren't in the dataclass
        fields = {field.name for field in dataclasses.fields(cls)}
        filtered_config = {k: v for k, v in overwrite_config.items() if k in fields}
        overwrite_config = cls(**filtered_config)
        return overwrite_config

    def __post_init__(self):
        assert self.llm_api_key is not None, "llm_api_key is required"
        if self.enable_event_embedding:
            if self.embedding_api_key is None and (
                self.llm_style == self.embedding_provider == "openai"
            ):
                # default to llm config if embedding_api_key is not set
                self.embedding_api_key = self.llm_api_key
                self.embedding_base_url = self.llm_base_url
            assert (
                self.embedding_api_key is not None
            ), "embedding_api_key is required for event embedding"

            if self.embedding_provider == "jina":
                self.embedding_base_url = (
                    self.embedding_base_url or "https://api.jina.ai/v1"
                )
                assert self.embedding_model in {
                    "jina-embeddings-v3",
                }, "embedding_model must be one of the following: jina-embeddings-v3"

        # Delay validation to avoid circular import at module load time
        # Validation will be done when actually needed
        pass

    @property
    def timezone(self) -> timezone:
        if self.use_timezone is None:
            return datetime.datetime.now().astimezone().tzinfo

        # For named timezones, we need to use the datetime.timezone.ZoneInfo
        return ZoneInfo(self.use_timezone)


# 1. Add logger
LOG = logging.getLogger("memobase_server")
LOG.setLevel(logging.INFO)


# Add standard formatter and handler
class Colors:
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    END = "\033[0m"


formatter = logging.Formatter(
    f"{Colors.BOLD}{Colors.BLUE}%(name)s |{Colors.END}  %(levelname)s - %(asctime)s  -  %(message)s"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
LOG.addHandler(handler)

# 2. Add encoder for tokenize strings
ENCODER = tiktoken.encoding_for_model("gpt-4o")



class ProjectLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(self, user_id: str, message: str):
        self.logger.debug(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message
        )

    def info(self, user_id: str, message: str):
        self.logger.info(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message
        )

    def warning(self, user_id: str, message: str):
        self.logger.warning(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message
        )

    def error(
        self, user_id: str, message: str, exc_info: bool = False
    ):
        self.logger.error(
            json.dumps({"user_id": str(user_id)})
            + " | "
            + message,
            exc_info=exc_info,
        )


TRACE_LOG = ProjectLogger(LOG)

# Config should be loaded by users, not globally
# But some legacy code still expects a global CONFIG, so provide a fallback
try:
    CONFIG = Config.load_config()
except Exception:
    # If no config file exists or API key is missing, create a minimal config
    CONFIG = None
