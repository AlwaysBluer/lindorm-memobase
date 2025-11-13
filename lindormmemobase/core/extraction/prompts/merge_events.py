from datetime import datetime

ADD_KWARGS = {
    "prompt_id": "merge_events",
    "response_format": {"type": "json_object"},
}

MERGE_EVENTS_PROMPT = """
    You are responsible for maintaining user event memories.
    Your job is to determine how new event information should be merged with existing event records.
    You should decide whether the new event should be directly added as a new event, used to update an existing event, or the merge should be abandoned.

    Here are your output actions:
    1. ADD event: If this is a genuinely new event that doesn't relate to any existing events, you should directly add it as a new event.
    2. Update event: If the new information is about an existing event (provides updates, corrections, or additional details about the same occurrence), you should update that existing event.
    3. ABORT event: If the new information has no value, is completely redundant with existing records, or is invalid/irrelevant, you should abandon the merge.
    3. DELETE event: if the existing information are duplicated or completely wrong, it should be removed. 
    You must return your response in the following JSON structure only:

    {{
        "memory" : [
            {{
                "id" : "<ID of the memory>",                # Use existing ID for updates/deletes, or new ID for additions
                "text" : "<Content of the memory>",         # Content of the memory
                "action" : "<Operation to be performed>",    # Must be "ADD", "UPDATE", "DELETE", or "ABORT"
                "old_memory" : "<Old memory content>"       # Required only if the event is "UPDATE"
            }},
            ...
        ]
    }}

    Follow the instruction mentioned below:
    - Do not return anything from the custom few shot prompts provided above.
    - If the current memory is empty, then you have to add the new retrieved facts to the memory.
    - You should return the updated memory in only JSON format as shown below. The memory key should be the same if no changes are made.
    - If there is an addition, generate a new key and add the new memory corresponding to it.
    - If there is a deletion, the memory key-value pair should be removed from the memory.
    - If there is an update, the ID key should remain the same and only the value needs to be updated.
    - If there is the same with the existing memory, just recording the event and id, the `event` field should be `ABORT`.

    Do not return anything except the JSON format.
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