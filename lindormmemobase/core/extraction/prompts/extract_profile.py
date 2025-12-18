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

DEFAULT_JOB = """You extract user profiles from memos in structured format.
Extract facts and preferences explicitly stated or reasonably inferred from the conversation.
Use the same language as the user's input.
"""

FACT_RETRIEVAL_PROMPT = """{system_prompt}

## Task
Extract user-related facts and preferences from the memo below. Focus on information about the user themselves, not other people mentioned.

## Input Context

**Topics Guidelines:** Use the provided topic/subtopic list as guidance. You may create new topics if necessary unless strict mode is enabled.

**User's Existing Topics:** Reuse existing topic/subtopic names when the same information appears again.

**Memo Format:** You'll receive a user memo (Markdown format) summarized from user-assistant conversations, containing user info, events, and preferences.

## Output Format
Output lines in this exact format:
```
- TOPIC{tab}SUB_TOPIC{tab}MEMO
```

Each line contains:
- **TOPIC**: Category of the information (e.g., basic_info, work, interest)
- **SUB_TOPIC**: Specific subcategory (e.g., name, title, hobby)
- **MEMO**: Extracted fact/preference about the user

Elements separated by `{tab}`, each line starts with `- `, separated by newlines.

## Examples
{examples}

## Critical Rules
- **Output ONLY profile lines** (no thinking, no explanations, no additional text)
- Extract facts with actual values only; skip if no value provided
- **Infer implied information**, not just explicit statements
- Group all content for same topic/sub_topic in ONE line (no duplicates)
- **Time handling:**
  - Use specific dates (YYYY/MM/DD), never relative terms ("today", "yesterday")
  - Distinguish mention time vs. event time: `[mention YYYY/MM/DD, happen at YYYY/MM/DD]`
  - If user mentions time-sensitive info, infer the specific date
- Return empty list if nothing relevant found
- **Language matching:** Record facts in the same language as user input
- **User-focused only:** Don't extract info about other people (e.g., if memo says "John is a manager", don't create work{tab}title unless it's about the user)

## Available Topics
{topic_examples}

Now extract profiles from the memo below.
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
