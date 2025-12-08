from ....config import TRACE_LOG
from ....core.constants import ConstantsTable
from ....core.storage.user_profiles import get_user_profiles 
from ....core.extraction.prompts.router import PROMPTS
from ....core.extraction.prompts.utils import (
    parse_string_into_profiles,
    attribute_unify,
)

from ....utils.tools import truncate_string

from ....models.response import AIUserProfiles
from ....models.profile_topic import ProfileConfig
from ....models.types import FactResponse

from ....models.profile_topic import read_out_profile_config
from ....llm.complete import llm_complete

def merge_by_topic_sub_topics(new_facts: list[FactResponse]):
    """Merge facts with same topic-subtopic using ;; separator for later splitting."""
    topic_subtopic = {}
    for nf in new_facts:
        key = (nf[ConstantsTable.topic], nf[ConstantsTable.sub_topic])
        if key in topic_subtopic and isinstance(nf["memo"], str):
            # Use ;; separator to preserve split boundaries
            topic_subtopic[key]["memo"] += f";; {nf['memo']}"
            continue
        topic_subtopic[key] = nf
    return list(topic_subtopic.values())


async def extract_topics(
    user_id: str, user_memo: str, project_profiles: ProfileConfig, config
) -> dict:
    profiles_data = await get_user_profiles(user_id, config)
    profiles = profiles_data.profiles
    USE_LANGUAGE = project_profiles.language or config.language
    STRICT_MODE = (
        project_profiles.profile_strict_mode
        if project_profiles.profile_strict_mode is not None
        else config.profile_strict_mode
    )

    project_profiles_slots = read_out_profile_config(
        project_profiles, PROMPTS[USE_LANGUAGE]["profile"].CANDIDATE_PROFILE_TOPICS, config
    )

    if STRICT_MODE:
        allowed_topic_subtopics = set()
        for p in project_profiles_slots:
            for st in p.sub_topics:
                allowed_topic_subtopics.add(
                    (attribute_unify(p.topic), attribute_unify(st["name"]))
                )

    if len(profiles):
        already_topics_subtopics = set(
            [
                (
                    attribute_unify(p.attributes[ConstantsTable.topic]),
                    attribute_unify(p.attributes[ConstantsTable.sub_topic]),
                )
                for p in profiles
            ]
        )
        already_topic_subtopics_values = {
            (
                attribute_unify(p.attributes[ConstantsTable.topic]),
                attribute_unify(p.attributes[ConstantsTable.sub_topic]),
            ): p.content
            for p in profiles
        }
        if STRICT_MODE:
            already_topics_subtopics = already_topics_subtopics.intersection(
                allowed_topic_subtopics
            )
            already_topic_subtopics_values = {
                k: already_topic_subtopics_values[k] for k in already_topics_subtopics
            }
        already_topics_subtopics = sorted(already_topics_subtopics)
        already_topics_prompt = "\n".join(
            [
                f"- {topic}{config.llm_tab_separator}{sub_topic}{config.llm_tab_separator}{truncate_string(already_topic_subtopics_values[(topic, sub_topic)], 10)}"
                for topic, sub_topic in already_topics_subtopics
            ]
        )
        TRACE_LOG.info(
            user_id,
            f"Already have {len(profiles)} profiles, {len(already_topics_subtopics)} topics",
        )
    else:
        already_topics_prompt = ""

    results = await llm_complete(
        PROMPTS[USE_LANGUAGE]["extract"].pack_input(
            already_topics_prompt,
            user_memo,
            strict_mode=STRICT_MODE,
        ),
        system_prompt=PROMPTS[USE_LANGUAGE]["extract"].get_prompt(
            PROMPTS[USE_LANGUAGE]["profile"].get_prompt(project_profiles_slots), config
        ),
        temperature=0.1,  # precise
        config=config,
        **PROMPTS[USE_LANGUAGE]["extract"].get_kwargs(),
    )
    parsed_facts: AIUserProfiles = parse_string_into_profiles(results)
    new_facts: list[FactResponse] = parsed_facts.model_dump()["facts"]
    if not len(new_facts):
        TRACE_LOG.info(
            user_id,
            f"No new facts extracted",
        )
        return {
            "fact_contents": [],
            "fact_attributes": [],
            "profiles": profiles,
            "total_profiles": project_profiles_slots,
        }

    for nf in new_facts:
        nf[ConstantsTable.topic] = attribute_unify(nf[ConstantsTable.topic])
        nf[ConstantsTable.sub_topic] = attribute_unify(nf[ConstantsTable.sub_topic])
    new_facts = merge_by_topic_sub_topics(new_facts)

    fact_contents = []
    fact_attributes = []

    for nf in new_facts:
        if STRICT_MODE:
            if (
                nf[ConstantsTable.topic],
                nf[ConstantsTable.sub_topic],
            ) not in allowed_topic_subtopics:
                continue
        fact_contents.append(nf["memo"])
        fact_attributes.append(
            {
                ConstantsTable.topic: nf[ConstantsTable.topic],
                ConstantsTable.sub_topic: nf[ConstantsTable.sub_topic],
            }
        )
    return {
        "fact_contents": fact_contents,
        "fact_attributes": fact_attributes,
        "profiles": profiles,
        "total_profiles": project_profiles_slots,
    }
