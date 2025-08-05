from config import Config
from models.profile_topic import ProfileConfig
from llm.openai_model_llm import openai_complete
from models.blob import Blob, BlobType

from core.extraction.prompts.router import PROMPTS
from core.extraction.prompts.utils import tag_chat_blobs_in_order_xml
from core.extraction.prompts.profile_init_utils import read_out_event_tags
from core.extraction.prompts.profile_init_utils import read_out_profile_config

from llm.complete import llm_complete
from utils.tools import Promise


async def entry_chat_summary(
    blobs: list[Blob], profile_config: ProfileConfig, config: Config
) -> Promise[str]:
    assert all(b.type == BlobType.chat for b in blobs), "All blobs must be chat blobs"
    USE_LANGUAGE = profile_config.language or config.language
    from core.extraction.prompts.user_profile_topics import get_candidate_profile_topics
    
    project_profiles_slots = read_out_profile_config(
        profile_config, get_candidate_profile_topics(config)
    )
    prompt = PROMPTS[USE_LANGUAGE]["entry_summary"]
    event_summary_theme = (
        profile_config.event_theme_requirement or config.event_theme_requirement
    )

    event_tags = read_out_event_tags(profile_config, config)
    event_attriubtes_str = "\n".join(
        [f"- {et.name}({et.description})" for et in event_tags]
    )
    from core.extraction.prompts.user_profile_topics import get_prompt
    profile_topics_str = get_prompt(project_profiles_slots)
    blob_strs = tag_chat_blobs_in_order_xml(blobs)
    r = await llm_complete(
        prompt.pack_input(blob_strs),
        system_prompt=prompt.get_prompt(
            profile_topics_str,
            event_attriubtes_str,
            additional_requirements=event_summary_theme,
        ),
        temperature=0.2,  # precise
        model=config.summary_llm_model,
        config=config,
        **prompt.get_kwargs(),
    )
    return r
