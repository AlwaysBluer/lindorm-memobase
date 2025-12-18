from . import user_profile_topics
from .utils import pack_profiles_into_string
from lindormmemobase.models.response import AIUserProfiles

ADD_KWARGS = {
    "prompt_id": "extract_profile",
}
EXAMPLES = [
    (
        """- User say Hi to assistant.
""",
        AIUserProfiles(**{"facts": []}),
    ),
    (
        """
- User is married to SiLei [mention 2025/01/15, happen at 2025/01/01]
""",
        AIUserProfiles(
            **{
                "facts": [
                    {
                        "topic": "demographics",
                        "sub_topic": "marital_status",
                        "memo": "married",
                    },
                    {
                        "topic": "life_event",
                        "sub_topic": "Marriage",
                        "memo": "married to SiLei [mention 2025/01/15, the marriage at 2025/01/01]",
                    },
                ]
            }
        ),
    ),
    (
        """
- User had a meeting with John at 3pm [mention 2024/10/11, the meeting at 2024/10/10]
- User is starting a project with John [mention 2024/10/11]
""",
        AIUserProfiles(
            **{
                "facts": [
                    {
                        "topic": "work",
                        "sub_topic": "collaboration",
                        "memo": "user is starting a project with John [mention 2024/10/11] and already met once [mention 2024/10/10]",
                    }
                ]
            }
        ),
    ),
    (
        """
- User is a software engineer at Memobase [mention 2025/01/01]
- User's name is John [mention 2025/01/01]
""",
        AIUserProfiles(
            **{
                "facts": [
                    {
                        "topic": "basic_info",
                        "sub_topic": "Name",
                        "memo": "John",
                    },
                    {
                        "topic": "work",
                        "sub_topic": "Title",
                        "memo": "user is a Software engineer [mention 2025/01/01]",
                    },
                    {
                        "topic": "work",
                        "sub_topic": "Company",
                        "memo": "user works at Memobase [mention 2025/01/01]",
                    },
                ]
            }
        ),
    ),
    (
        """
- User's favorite movies are Inception and Interstellar [mention 2025/01/01]
- User's favorite movie is Tenet [mention 2025/01/02]
""",
        AIUserProfiles(
            **{
                "facts": [
                    {
                        "topic": "interest",
                        "sub_topic": "Movie",
                        "memo": "Inception, Interstellar[mention 2025/01/01]; favorite movie is Tenet [mention 2025/01/02]",
                    },
                    {
                        "topic": "interest",
                        "sub_topic": "movie_director",
                        "memo": "user seems to be a big fan of director Christopher Nolan",
                    },
                ]
            }
        ),
    ),
]

DEFAULT_JOB = """You are a user profile extraction specialist.
Your task is to extract structured profile information from user memos.
Extract both explicitly stated facts and reasonably inferred information.
Record facts in the same language as the user's input.
"""

FACT_RETRIEVAL_PROMPT = """{system_prompt}

## Task Overview
Extract user-related facts and preferences from memos into structured profiles.

## Input Structure

### Available Topics
Below are the recommended topics/subtopics for extraction:
{topic_examples}

### Existing User Topics
Topics already recorded for this user (use consistent naming):
{{already_input}}

### User Memo
The memo to extract from (summarized from user-assistant conversations).

## Output Format

### Step 1: Analysis
Briefly identify what topics/subtopics are mentioned or can be inferred.

### Step 2: Extraction
Output each fact as a markdown list item:
```
- TOPIC{tab}SUB_TOPIC{tab}MEMO
```

Example:
```
- basic_info{tab}name{tab}John
- work{tab}title{tab}Software engineer at Memobase [mention 2025/01/01]
```

## Extraction Rules
1. **User-centric**: Only extract information about the USER, not others mentioned
2. **Time handling**: Preserve time annotations `[mention DATE, happen DATE]`
3. **Deduplication**: Consolidate related facts under the same topic/subtopic
4. **Inference**: Extract implied information (e.g., multiple Nolan movies → likes Nolan)
5. **Completeness**: Include all relevant facts, but no fabrication
6. **Language**: Match the user's input language

## Examples
{examples}

Now extract profiles from the following memo:
"""


def pack_input(already_input, memo_str, strict_mode: bool = False):
    header = ""
    if strict_mode:
        header = "**STRICT MODE**: Only use topics/subtopics from Topics Guidelines. Creating new topics will invalidate your answer."
    return f"""{header}

**User's Existing Topics:**
{already_input}

**Memo:**
{memo_str}
"""


def get_default_profiles() -> str:
    return user_profile_topics.get_prompt()


def get_prompt(topic_examples: str, config) -> str:
    sys_prompt = config.system_prompt or DEFAULT_JOB
    examples = "\n\n".join(
        [
            f"""<example>
<input>{p[0]}</input>
<output>
{pack_profiles_into_string(p[1])}
</output>
</example>
"""
            for p in EXAMPLES
        ]
    )
    return FACT_RETRIEVAL_PROMPT.format(
        system_prompt=sys_prompt,
        examples=examples,
        tab=config.llm_tab_separator,
        topic_examples=topic_examples,
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(get_prompt(get_default_profiles()))
