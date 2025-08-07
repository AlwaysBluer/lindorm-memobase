import asyncio
from collections import defaultdict
from ....config import TRACE_LOG

from ....core.extraction.prompts.router import PROMPTS
from ....core.extraction.prompts.profile_init_utils import get_specific_subtopics
from ....models.types import MergeAddResult, ProfileData, AddProfile
from ....models.profile_topic import ProfileConfig
from ....core.constants import ConstantsTable
from ....core.extraction.prompts.utils import (
    parse_string_into_subtopics,
    attribute_unify,
)

from ....llm.complete import llm_complete


from ....models.promise import Promise


async def organize_profiles(
    user_id: str,
    profile_options: MergeAddResult,
    config: ProfileConfig,
    main_config,
) -> Promise[None]:
    profiles = profile_options["before_profiles"]
    USE_LANGUAGE = config.language or main_config.language
    topic_groups = defaultdict(list)
    for p in profiles:
        topic_groups[p.attributes[ConstantsTable.topic]].append(p)

    need_to_organize_topics: dict[str, list[ProfileData]] = {}
    for topic, group in topic_groups.items():
        if len(group) > main_config.max_profile_subtopics:
            need_to_organize_topics[topic] = group

    if not len(need_to_organize_topics):
        return Promise.resolve(None)
    ps = await asyncio.gather(
        *[
            organize_profiles_by_topic(user_id, group, USE_LANGUAGE, main_config)
            for group in need_to_organize_topics.values()
        ]
    )
    if not all([p.ok() for p in ps]):
        errmsg = "\n".join([p.msg() for p in ps if not p.ok()])
        return Promise.reject(f"Failed to organize profiles: {errmsg}")

    delete_profile_ids = []
    for gs in need_to_organize_topics.values():
        delete_profile_ids.extend([p.id for p in gs])
    new_profiles = []
    for p in ps:
        new_profiles.extend(p.data())

    profile_options["add"].extend(new_profiles)
    profile_options["add"] = deduplicate_profiles(profile_options["add"])
    profile_options["delete"].extend(delete_profile_ids)
    return Promise.resolve(None)


async def organize_profiles_by_topic(
    user_id: str,
    profiles: list[ProfileData],
    USE_LANGUAGE: str,  # profiles in the same topics
    main_config,
) -> Promise[list[AddProfile]]:
    assert (
        len(profiles) > main_config.max_profile_subtopics
    ), f"Unknown Error,{len(profiles)} is not greater than max_profile_subtopics: {main_config.max_profile_subtopics}"
    assert all(
        p.attributes[ConstantsTable.topic] == profiles[0].attributes[ConstantsTable.topic]
        for p in profiles
    ), f"Unknown Error, all profiles are not in the same topic: {profiles[0].attributes['topic']}"
    TRACE_LOG.info(
        user_id,
        f"Organizing profiles for topic: {profiles[0].attributes['topic']} with sub_topics {len(profiles)}",
    )
    topic = attribute_unify(profiles[0].attributes[ConstantsTable.topic])
    suggest_subtopics = get_specific_subtopics(
        topic, PROMPTS[USE_LANGUAGE]["profile"].CANDIDATE_PROFILE_TOPICS
    )

    llm_inputs = "\n".join(
        [
            f"- {p.attributes['sub_topic']}{main_config.llm_tab_separator}{p.content}"
            for p in profiles
        ]
    )
    llm_prompt = f"""topic: {topic}
{llm_inputs}
"""
    p = await llm_complete(
        llm_prompt,
        PROMPTS[USE_LANGUAGE]["organize"].get_prompt(
            main_config.max_profile_subtopics // 2 + 1, suggest_subtopics
        ),
        temperature=0.2,  # precise
        config=main_config,
        **PROMPTS[USE_LANGUAGE]["organize"].get_kwargs(),
    )
    if not p.ok():
        return p
    results = p.data()
    subtopics = parse_string_into_subtopics(results)
    reorganized_profiles: list[AddProfile] = [
        {
            "content": sp["memo"],
            "attributes": {
                ConstantsTable.topic: topic,
                ConstantsTable.sub_topic: sp[ConstantsTable.sub_topic],
            },
        }
        for sp in subtopics
    ]
    if len(reorganized_profiles) == 0:
        return Promise.reject(
            "Failed to organize profiles, left profiles is 0 so maybe it's the LLM error"
        )
    # forcing the number of subtopics to be less than max_profile_subtopics // 2 + 1
    reorganized_profiles = reorganized_profiles[: main_config.max_profile_subtopics // 2 + 1]
    return Promise.resolve(reorganized_profiles)


def deduplicate_profiles(profiles: list[AddProfile]) -> list[AddProfile]:
    topic_subtopic = {}
    for nf in profiles:
        key = (
            nf["attributes"][ConstantsTable.topic],
            nf["attributes"][ConstantsTable.sub_topic],
        )
        if key in topic_subtopic:
            topic_subtopic[key]["content"] += f"; {nf['content']}"
            continue
        topic_subtopic[key] = nf
    return list(topic_subtopic.values())
