from datetime import datetime

ADD_KWARGS = {
    "prompt_id": "zh_merge_events",
    "response_format": {"type": "json_object"},
}

MERGE_EVENTS_PROMPT = """你是事件记忆管理专家。你的任务是将新事件信息与现有记录合并。

## 决策框架

对每个新事件，决定执行一个操作：

| 操作 | 使用场景 |
|------|----------|
| **ADD** | 全新事件，与现有事件无关 |
| **UPDATE** | 新信息更新、修正或补充现有事件 |
| **DELETE** | 现有事件重复或完全错误 |
| **ABORT** | 新信息冗余、无效或无价值 |

## 输出格式

仅返回 JSON 对象：
```json
{{
    "memory": [
        {{
            "id": "<事件ID>",
            "text": "<事件内容>",
            "action": "ADD|UPDATE|DELETE|ABORT",
            "old_memory": "<原内容>"  // 仅 UPDATE 时需要
        }}
    ]
}}
```

## 规则
1. ADD：生成新的唯一ID
2. UPDATE/DELETE：使用现有事件的ID
3. ABORT：记录事件ID，action设为"ABORT"
4. `old_memory` 仅在 UPDATE 时必填
5. 如果无现有事件，执行 ADD
6. 仅返回 JSON，不输出其他文本
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
        existing_events: 现有的相关事件列表，每个元素是包含 'id' 和 'text' 的字典
            格式: [{"id": "event_123", "text": "事件描述"}, ...]
        config: 系统配置对象，用于获取时区等信息

    Returns:
        格式化的输入字符串
    """
    today = datetime.now().strftime("%Y-%m-%d") if config is None else datetime.now().astimezone(
        config.timezone).strftime("%Y-%m-%d")

    if existing_events and len(existing_events) > 0:
        existing_events_str = "\n".join([
            f"事件 #{event['id']}: {event['text']}"
            for event in existing_events
        ])
    else:
        existing_events_str = "[暂无现有事件]"

    return f"""今天是 {today}。
        ## 现有相关事件
            {existing_events_str}

        ## 新事件信息
           {new_event_content}
        """


def get_prompt() -> str:
    return MERGE_EVENTS_PROMPT


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(get_prompt())
