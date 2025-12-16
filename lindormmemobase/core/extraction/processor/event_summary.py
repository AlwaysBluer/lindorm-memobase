from typing import Optional
from lindormmemobase.models.profile_topic import ProfileConfig

from lindormmemobase.core.extraction.prompts.utils import(
    parse_string_into_subtopics,
    attribute_unify
)
from lindormmemobase.core.extraction.prompts.profile_init_utils import read_out_event_tags 
from lindormmemobase.core.extraction.prompts import event_tagging as event_tagging_prompt

from lindormmemobase.llm.complete import llm_complete
from lindormmemobase.utils.errors import ExtractionError


async def tag_event(
    profile_config: ProfileConfig, event_summary: str, main_config=None
) -> Optional[list]:
    event_tags = read_out_event_tags(profile_config, main_config)
    available_event_tags = set([et.name for et in event_tags])
    if len(event_tags) == 0:
        return None
    event_tags_str = "\n".join([f"- {et.name}({et.description})" for et in event_tags])
    try:
        r = await llm_complete(
            event_summary,
            system_prompt=event_tagging_prompt.get_prompt(event_tags_str),
            temperature=0.2,
            model=main_config.event_llm_model or main_config.best_llm_model if main_config else "qwen-max-latest",
            config=main_config,
            **event_tagging_prompt.get_kwargs(),
        )
        parsed_event_tags = parse_string_into_subtopics(r)
        parsed_event_tags = [
            {"tag": attribute_unify(et["sub_topic"]), "value": et["memo"]}
            for et in parsed_event_tags
        ]
        strict_parsed_event_tags = [
            et for et in parsed_event_tags if et["tag"] in available_event_tags
        ]
        return strict_parsed_event_tags
    except Exception as e:
        raise ExtractionError(f"Failed to tag event: {str(e)}") from e
