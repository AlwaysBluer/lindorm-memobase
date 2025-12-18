from datetime import datetime

ADD_KWARGS = {
    "prompt_id": "merge_profile",
}

MERGE_FACTS_PROMPT = """You maintain user memos by merging new information with existing content.

## Decision Rules
Choose ONE action based on the supplementary information:

1. **APPEND** - Use when:
   - New info adds facts not in current memo
   - Current memo is empty and new info matches topic

2. **UPDATE** - Use when:
   - New info conflicts with current memo (replace outdated content)
   - Need to combine old + new info into unified memo
   - Current memo has removable/simplifiable parts

3. **ABORT** - Use when:
   - New info doesn't match topic/subtopic description
   - Info already fully covered in current memo
   - New info has no value

## Considerations
- Check if new info matches topic description; if not, try to extract relevant parts or ABORT
- If update instruction exists, follow it
- When updating, remove outdated/redundant content
- Preserve time annotations from both old and new memos

## Output Format
Output **exactly one line** starting with `- ` in one of these formats:

```
- APPEND{tab}APPEND
```
```
- UPDATE{tab}[COMPLETE_UPDATED_MEMO]
```
```
- ABORT{tab}ABORT
```

## Examples

**Example 1: APPEND**
Current: "User likes hiking [mentioned 2025/01/05]"
New: "User enjoys photography"
Output:
```
- APPEND{tab}APPEND
```

**Example 2: UPDATE**
Current: "Preparing for midterm exams [mentioned 2025/03/10]; Learning Python"
New: "Preparing for final exams"
Output:
```
- UPDATE{tab}Learning Python; Preparing for final exams [mentioned 2025/06/01]
```

**Example 3: ABORT**
Topic: "Career Goals"
Current: "Wants to become a software engineer"
New: "User likes pizza" (irrelevant to topic)
Output:
```
- ABORT{tab}ABORT
```

## Critical Rules
- Output ONLY the action line (no explanations, no numbered lists, no additional text)
- Keep final memo ≤5 sentences, concise and factual
- Never fabricate content not in input
- Preserve time annotations: [mentioned on YYYY/MM/DD] or [occurred in YYYY]
- Remove redundancy when updating

Now process the input below.
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
