"""Profile config resolver - Resolve ProfileConfig with DB lookup and fallback.

This module provides the resolve_profile_config function that implements
the three-tier priority: user_config > DB config > main config (YAML).
"""
from typing import Optional

from lindormmemobase.config import Config, LOG
from lindormmemobase.models.profile_topic import ProfileConfig

DEFAULT_PROJECT_ID = "default"


async def resolve_profile_config(
    project_id: Optional[str],
    user_config: Optional[ProfileConfig],
    topic_config_storage: 'TopicConfigStorage',
    main_config: Config
) -> ProfileConfig:
    """
    Resolve ProfileConfig for a request with DB lookup and fallback.

    Priority order:
    1. user_config (explicitly provided by caller) - highest priority
    2. DB config (from ProjectProfileConfigs table)
    3. main_config (from config.yaml) - fallback

    Args:
        project_id: Project identifier (None means use default)
        user_config: ProfileConfig explicitly provided by caller (takes priority)
        topic_config_storage: Storage for DB lookup
        main_config: Global Config object (fallback)

    Returns:
        Resolved ProfileConfig object
    """
    # Priority 1: Explicit user config (highest)
    if user_config is not None:
        LOG.debug(f"Using user-provided ProfileConfig for project {project_id}")
        return user_config

    # Priority 2: DB config
    actual_project_id = project_id or DEFAULT_PROJECT_ID
    try:
        db_config = await topic_config_storage.get_profile_config(actual_project_id)
        if db_config is not None:
            LOG.info(f"Using DB config for project {actual_project_id}")
            return db_config
        LOG.info(f"No DB config found for project {actual_project_id}")
    except Exception as e:
        LOG.warning(f"Failed to load DB config for project {actual_project_id}: {e}")

    # Priority 3: Fallback to main config (config.yaml)
    LOG.info(f"Falling back to main config for project {actual_project_id}")
    return ProfileConfig.load_from_config(main_config)
