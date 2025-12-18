# Remove CONFIG import

ADD_KWARGS = {
    "prompt_id": "event_tagging",
}
EXAMPLES = [
    (
        """
## Assume the event tags are:
## - emotion(the user's current emotion)
## - goals(the user's goals)
## - location(the location of user)
The assistant passionately expresses their love and care for the user, trying to convince them that their feelings are genuine and not just physical, despite the user's skepticism and demand for proof.
""",
        """- emotion{tab}skepticism about the assistant's love
- goals{tab}Demand proof of assistant's love
""",
        """The event mentioned the users' feelings and demands, so the `emotion` and `goals` tags can be filled,
But the location is not mentioned, so it's not included in the result.
""",
    )
]

FACT_RETRIEVAL_PROMPT = """You are an event tagging specialist. Extract specific tag values from event summaries.

## Available Tags
<event_tags>
{event_tags}
</event_tags>

Tag format: `tag_name(description)`
Example: `emotion(the user's current emotion)` → tag name is `emotion`

## Output Format
```
- TAG{tab}VALUE
```

Example:
```
- emotion{tab}sad
- goals{tab}find a new home
```

## Rules
1. Use exact tag names as provided - do not modify them
2. Only include tags that are mentioned or implied in the summary
3. Skip tags with no relevant information
4. Match output language to input language

## Examples
{examples}

Extract tags from the following event summary:
"""


def get_prompt(event_tags: str, config=None) -> str:
    examples = "\n\n".join(
        [
            f"""<input>{p[0]}</input>
<output>{p[1]}</output>
<explanation>{p[2]}</explanation>
"""
            for p in EXAMPLES
        ]
    )
    return FACT_RETRIEVAL_PROMPT.format(
        examples=examples.format(tab=config.llm_tab_separator if config else "::"),
        tab=config.llm_tab_separator if config else "::",
        event_tags=event_tags,
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(
        get_prompt(
            event_tags="""- 冒险
- 天气
- 休息
- 逃离
""",
        )
    )
