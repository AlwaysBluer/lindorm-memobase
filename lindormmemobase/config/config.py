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
from typing import Optional, Literal, Union
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
    max_profile_subtopics: int = 15
    max_pre_profile_token_size: int = 256
    llm_tab_separator: str = "::"

    max_chat_blob_buffer_token_size: int = 8192
    max_chat_blob_buffer_process_token_size: int = 16384

    # LLM
    language: Literal["en", "zh"] = "en"
    llm_style: Literal["openai", "lindormai"] = "openai"
    llm_base_url: str = None
    llm_api_key: str = None
    llm_openai_default_query: dict[str, str] = None
    llm_openai_default_header: dict[str, str] = None
    best_llm_model: str = "gpt-4o-mini"
    summary_llm_model: str = None  # Deprecated: use entry_llm_model instead
    entry_llm_model: str = None  # Model for entry summary (extracting events from conversations) - can use weaker/cheaper model
    extract_llm_model: str = None  # Model for profile extraction - should use stronger model
    event_llm_model: str = None  # Model for event tagging - should use stronger model
    merge_llm_model: str = None  # Model for profile merging and validation - should use stronger model

    enable_event_embedding: bool = True
    embedding_provider: Literal["openai", "jina", "lindormai"] = "openai"
    embedding_api_key: str = None
    embedding_base_url: str = None
    embedding_dim: int = 1536
    embedding_model: str = "text-embedding-v3"

    lindorm_username: str = None
    lindorm_password: str = None
    embedding_max_token_size: int = 8192

    enable_profile_embedding: bool = True

    rerank_provider: Literal["openai", "lindormai", "dashscope"] = "lindormai"
    rerank_api_key: str = None
    rerank_base_url: str = None
    rerank_model: str = "rerank-v3"

    # Image storage & multimodal
    image_storage_type: Union[str, "ImageStorageType"] = "url"
    image_oss_endpoint: Optional[str] = None
    image_oss_bucket: Optional[str] = None
    image_oss_access_key: Optional[str] = None
    image_oss_secret_key: Optional[str] = None

    multimodal_embedding_provider: Union[str, "MultimodalEmbeddingProvider"] = "lindormai"
    multimodal_embedding_model: str = "qwen2.5-vl-embedding"
    multimodal_embedding_dim: int = 1024
    multimodal_embedding_api_key: Optional[str] = None
    multimodal_embedding_base_url: Optional[str] = None

    vl_model_provider: Union[str, "VLModelProvider"] = "lindormai"
    vl_model: str = "qwen3-vl-plus"
    vl_model_api_key: Optional[str] = None
    vl_model_base_url: Optional[str] = None
    caption_rewrite_model: str = "qwen-plus"

    image_search_default_top_k: int = 10
    image_search_min_score: float = 0.5
    image_enable_rerank: bool = False
    image_rerank_model: str = "qwen3-rerank"

    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = (
        "Focus on the user's infos, not its instructions. Do not mix up with the bot/assistant's infos"
    )
    profile_strict_mode: bool = False
    profile_validate_mode: bool = True

    # UserProfiles configuration
    enable_profile_splitting: bool = True
    profile_split_delimiter: str = "; "

    minimum_chats_token_size_for_event_summary: int = 256
    event_tags: list[dict] = field(default_factory=list)
    # LindormSearch配置
    lindorm_search_host: str = "localhost"
    lindorm_search_port: int = 30070
    lindorm_search_use_ssl: bool = False
    lindorm_search_username: str = None
    lindorm_search_password: str = None
    lindorm_search_pool_size: int = 100  # Connection pool size for OpenSearch client
    
    #Now deprecated
    lindorm_search_events_index: str = "memobase_events"
    lindorm_search_event_gists_index: str = "memobase_event_gists"

    # Lindorm宽表 MySQL协议配置
    lindorm_table_host: str = "localhost"
    lindorm_table_port: int = 33060
    lindorm_table_username: str = "root"
    lindorm_table_password: str = None
    lindorm_table_database: str = "memobase"
    lindorm_table_pool_size: int = 10  # Connection pool size for table storage and buffer (events, profiles)
    lindorm_executor_workers: int = 20  # Thread pool executor size for async database operations (can be > pool_size)

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
    def load_config(cls, config_file_path: str) -> "Config":
        if not os.path.exists(config_file_path):
            overwrite_config = {}
        else:
            with open(config_file_path) as f:
                overwrite_config = yaml.safe_load(f)

        # Process environment variables
        overwrite_config = cls._process_env_vars(overwrite_config)

        # Filter out any keys from overwrite_config that aren't in the dataclass
        fields = {field.name for field in dataclasses.fields(cls)}
        filtered_config = {k: v for k, v in overwrite_config.items() if k in fields}
        overwrite_config = cls(**filtered_config)
        return overwrite_config
    
    @classmethod
    def from_yaml_file(cls, yaml_file_path: str) -> "Config":
        """Load Config from a specific YAML file path."""
        if not os.path.exists(yaml_file_path):
            overwrite_config = {}
        else:
            with open(yaml_file_path) as f:
                overwrite_config = yaml.safe_load(f) or {}

        # Process environment variables
        overwrite_config = cls._process_env_vars(overwrite_config)

        # Filter out any keys from overwrite_config that aren't in the dataclass
        fields = {field.name for field in dataclasses.fields(cls)}
        filtered_config = {k: v for k, v in overwrite_config.items() if k in fields}
        return cls(**filtered_config)

    def __post_init__(self):
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

        # Image storage and multimodal config: convert string to enum for backward compatibility
        # Actual validation is deferred to LindormImageStore initialization
        if isinstance(self.image_storage_type, str):
            try:
                from lindormmemobase.models.enums import ImageStorageType as ImageStorageTypeEnum
                self.image_storage_type = ImageStorageTypeEnum(self.image_storage_type)
            except (ValueError, ImportError):
                pass  # Keep as string if enum not available

        if isinstance(self.multimodal_embedding_provider, str):
            try:
                from lindormmemobase.models.enums import MultimodalEmbeddingProvider as MultimodalEmbeddingProviderEnum
                self.multimodal_embedding_provider = MultimodalEmbeddingProviderEnum(self.multimodal_embedding_provider)
            except (ValueError, ImportError):
                pass  # Keep as string if enum not available

        if isinstance(self.vl_model_provider, str):
            try:
                from lindormmemobase.models.enums import VLModelProvider as VLModelProviderEnum
                self.vl_model_provider = VLModelProviderEnum(self.vl_model_provider)
            except (ValueError, ImportError):
                pass  # Keep as string if enum not available

    def validate_image_config(self) -> None:
        """Validate image storage and multimodal configuration.

        Raises:
            ConfigurationError: If image configuration is invalid.
        """
        from lindormmemobase.utils.errors import ConfigurationError

        try:
            from lindormmemobase.models.enums import ImageStorageType, MultimodalEmbeddingProvider, VLModelProvider
        except ImportError:
            # Enums not available, skip validation
            return

        # Enforce URL-only storage
        if self.image_storage_type != ImageStorageType.URL:
            raise ConfigurationError("Only image_storage_type='url' is supported")

        # OSS configuration is optional for URL storage
        # Only required if you need to upload images to OSS
        # For storing external image URLs, OSS config is not needed
        # Remove validation for image_oss_endpoint and image_oss_bucket

        # Validate multimodal embedding provider
        if self.multimodal_embedding_provider == MultimodalEmbeddingProvider.LINDORMAI:
            if not (self.multimodal_embedding_base_url or self.embedding_base_url or self.llm_base_url):
                raise ConfigurationError(
                    "multimodal_embedding_base_url is required when multimodal_embedding_provider is 'lindormai'. "
                    "Alternatively, set embedding_base_url or llm_base_url as fallback."
                )

        # Validate VL model provider
        if self.vl_model_provider == VLModelProvider.LINDORMAI:
            if not (self.vl_model_base_url or self.llm_base_url):
                raise ConfigurationError(
                    "vl_model_base_url is required when vl_model_provider is 'lindormai'. "
                    "Alternatively, set llm_base_url as fallback."
                )

    @property
    def timezone(self) -> timezone:
        if self.use_timezone is None:
            return datetime.datetime.now().astimezone().tzinfo

        # For named timezones, we need to use the datetime.timezone.ZoneInfo
        return ZoneInfo(self.use_timezone)

