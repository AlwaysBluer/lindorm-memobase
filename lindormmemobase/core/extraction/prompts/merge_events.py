from datetime import datetime

ADD_KWARGS = {
    "prompt_id": "merge_events",
    "response_format": {"type": "json_object"},
}

MERGE_EVENTS_PROMPT = """You are an event memory manager. Your task is to merge new event information with existing records.

## Decision Framework

For each new event, decide ONE action:

| Action | When to Use |
|--------|-------------|
| **ADD** | Genuinely new event, unrelated to any existing events |
| **UPDATE** | New info updates, corrects, or supplements an existing event |
| **DELETE** | Existing event is duplicate or completely incorrect |
| **ABORT** | New info is redundant, invalid, or adds no value |

## Output Format

Return ONLY a JSON object:
```json
{{
    "memory": [
        {{
            "id": "<event_id>",
            "text": "<event_content>",
            "action": "ADD|UPDATE|DELETE|ABORT",
            "old_memory": "<previous_content>"  // Only for UPDATE
        }}
    ]
}}
```

## Rules
1. For ADD: Generate a new unique ID
2. For UPDATE/DELETE: Use the existing event's ID
3. For ABORT: Record the event ID and set action to "ABORT"
4. `old_memory` is required ONLY for UPDATE action
5. If no existing events, ADD the new event
6. Return ONLY the JSON, no additional text
"""


def get_input(
        new_event_content: str,
        existing_events: list[dict] = None,
        config=None
):
    """
    生成传递给 LLM 的输入内容

    Args:
        new_event_content: 新的事件内容（字符串）
        existing_events: 现有的相关事件列表，每个元素是包含 'id' 和 'content' 的字典
            格式: [{"id": "event_123", "content": "事件描述"}, ...]
        config: 系统配置对象，用于获取时区等信息

    Returns:
        格式化的输入字符串
    """
    today = datetime.now().strftime("%Y-%m-%d") if config is None else datetime.now().astimezone(
        config.timezone).strftime("%Y-%m-%d")

    if existing_events and len(existing_events) > 0:
        existing_events_str = "\n".join([
            f"Event #{event['id']}: {event['text']}"
            for event in existing_events
        ])
    else:
        existing_events_str = "[No existing events]"

    return f"""Today is {today}.
        ## Existing Related Events
            {existing_events_str}

        ## New Event Information
           {new_event_content}
        """


def get_prompt() -> str:
    return MERGE_EVENTS_PROMPT


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "main":
    print(get_prompt())