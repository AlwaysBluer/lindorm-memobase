from typing import Optional
from models.profile_topic import ProfileConfig

from core.extraction.prompts.utils import(
    parse_string_into_subtopics,
    attribute_unify
)
from core.extraction.prompts.profile_init_utils import read_out_event_tags 
from core.extraction.prompts import event_tagging as event_tagging_prompt

from utils.promise import Promise
from llm.complete import llm_complete


async def tag_event(
    profile_config: ProfileConfig, event_summary: str, main_config=None
) -> Promise[Optional[list]]:
    event_tags = read_out_event_tags(profile_config, main_config)
    available_event_tags = set([et.name for et in event_tags])
    if len(event_tags) == 0:
        return Promise.resolve(None)
    event_tags_str = "\n".join([f"- {et.name}({et.description})" for et in event_tags])
    r = await llm_complete(
        event_summary,
        system_prompt=event_tagging_prompt.get_prompt(event_tags_str),
        temperature=0.2,
        model=main_config.best_llm_model if main_config else "gpt-4o-mini",
        config=main_config,
        **event_tagging_prompt.get_kwargs(),
    )
    if not r.ok():
        return r
    parsed_event_tags = parse_string_into_subtopics(r.data())
    parsed_event_tags = [
        {"tag": attribute_unify(et["sub_topic"]), "value": et["memo"]}
        for et in parsed_event_tags
    ]
    strict_parsed_event_tags = [
        et for et in parsed_event_tags if et["tag"] in available_event_tags
    ]
    return Promise.resolve(strict_parsed_event_tags)
