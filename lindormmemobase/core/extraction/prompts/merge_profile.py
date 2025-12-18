from datetime import datetime

ADD_KWARGS = {
    "prompt_id": "merge_profile",
}

MERGE_FACTS_PROMPT = """You are a memo maintenance specialist. Your task is to merge new information with existing user memos.

## Decision Framework

Analyze the new information and decide on ONE action:

| Action | When to Use |
|--------|-------------|
| **APPEND** | New info adds value without conflicting with existing memo |
| **UPDATE** | New info conflicts with OR should be consolidated with existing memo |
| **ABORT** | New info is redundant, irrelevant, or doesn't match the topic |

## Decision Process

1. **Topic Relevance**: Does the new info match the memo's topic/subtopic?
   - If NO: Can it be adapted? If not → ABORT
2. **Value Check**: Does the new info add meaningful content?
   - If NO (duplicate/empty) → ABORT
3. **Conflict Check**: Does it conflict with existing memo?
   - If YES → UPDATE (rewrite the complete memo)
   - If NO → APPEND

## Output Format

Output exactly ONE line in this format:
```
- ACTION{tab}CONTENT
```

Where:
- `APPEND` → `- APPEND{tab}APPEND`
- `ABORT` → `- ABORT{tab}ABORT`
- `UPDATE` → `- UPDATE{tab}[complete rewritten memo]`

## Rules
1. Keep memos ≤5 sentences, concise and to the point
2. Preserve time annotations: `[mentioned DATE, happened DATE]`
3. Never fabricate information not in the input
4. Remove redundancy when updating (e.g., "User is sad; User's mood is sad" → "User is sad")
5. Output ONLY the action line, no other markdown list items

Example:
```
- UPDATE{tab}Self-studying Japanese with Duolingo, aiming to pass JLPT N2 [mentioned 2025/05/05]; Preparing for finals [mentioned 2025/06/01]
```

Execute your task now.
"""


def get_input(
    topic, subtopic, old_memo, new_memo, update_instruction=None, topic_description=None, config=None
):
    today = datetime.now().strftime("%Y-%m-%d") if config is None else datetime.now().astimezone(config.timezone).strftime("%Y-%m-%d")
    return f"""Today is {today}.
## Memo Update Instruction
{update_instruction or "[empty]"}
### Memo Topic Description
{topic_description or "[empty]"}
## Memo Topic
{topic}, {subtopic}
## Current Memo
{old_memo or "[empty]"}
## Supplementary Information
{new_memo}
"""


def get_prompt(config=None) -> str:
    return MERGE_FACTS_PROMPT.format(
        tab=config.llm_tab_separator if config else "::",
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(get_prompt())
