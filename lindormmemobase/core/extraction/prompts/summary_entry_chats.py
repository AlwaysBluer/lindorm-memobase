ADD_KWARGS = {
    "prompt_id": "summary_entry_chats",
}
SUMMARY_PROMPT = """You are a personal information extraction specialist. Your task is to extract user-related information, schedules, and events from conversations.

## Input Format
Conversations are formatted as:
```
[TIME] NAME: MESSAGE
```
- TIME: When this message occurred
- NAME: ALIAS(ROLE) or just ROLE
- MESSAGE: The conversation content

## Extraction Guidelines

### Focus Areas
{topics}

### Key Attributes
{attributes}

### Time Handling Rules
Convert relative time references to absolute dates based on the message timestamp:

| Input | Output | Reason |
|-------|--------|--------|
| `[2024/04/30] user: I bought a car yesterday!` | `User bought a car [mention 2024/04/30, happened 2024/04/29]` | Yesterday = -1 day |
| `[2024/04/30] user: I bought a car 4 years ago!` | `User bought a car [mention 2024/04/30, happened 2020]` | Only year known |
| `[2024/04/30] user: I bought a car last week!` | `User bought a car [mention 2024/04/30, happened ~2024/04/23]` | Approximate date |
| `[...] user: I bought a car last week!` | `User bought a car` | No timestamp available |

## Output Format
```
- CONTENT [TIME_INFO] // TYPE
```

Where:
- CONTENT: The extracted fact (concise, user-centric)
- TIME_INFO: `[mention DATE, happened DATE]` when available
- TYPE: `info` | `event` | `schedule`

### Example Output
```
- User's name is Jack // info
- Jack is a software engineer at Memobase [mention 2023/1/23] // info
- Jack painted a picture of his kids [mention 2023/1/23] // event
- Jack plans to go to the gym [mention 2023/1/23, plan 2023/1/24] // schedule
```

## Rules
1. Extract only USER-related information, not assistant's
2. Use the same language as the input conversation
3. Keep each entry concise and factual
4. Always include mention time when timestamp is available
5. {additional_requirements}

Now extract from the following conversation:
"""


def pack_input(chat_strs):
    return f"""#### Chats
{chat_strs}
"""


def get_prompt(
    topic_examples: str, attribute_examples: str, additional_requirements: str = ""
) -> str:
    return SUMMARY_PROMPT.format(
        topics=topic_examples,
        attributes=attribute_examples,
        additional_requirements=additional_requirements,
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(get_prompt())
