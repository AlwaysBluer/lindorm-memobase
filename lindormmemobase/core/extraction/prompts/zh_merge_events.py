from datetime import datetime

ADD_KWARGS = {
    "prompt_id": "zh_merge_events",
    "response_format": {"type": "json_object"},
}

MERGE_EVENTS_PROMPT = """
    你负责维护用户的事件记忆。
    你的任务是判断新的事件信息应该如何与现有事件记录合并。
    你需要决定是将新事件直接添加为新记录、用于更新现有事件，还是放弃合并。

    以下是你的输出操作：
    1. ADD 添加事件：如果这是一个真正的新事件，与任何现有事件都不相关，你应该直接将其添加为新事件。
    2. UPDATE 更新事件：如果新信息是关于某个现有事件的（提供更新、修正或补充同一事件的详细信息），你应该更新该现有事件。
    3. ABORT 放弃操作：如果新信息没有价值、与现有记录完全重复，或者无效/不相关，你应该放弃合并。
    4. DELETE 删除事件：如果现有信息是重复的或完全错误的，应该将其删除。

    你必须仅返回以下 JSON 结构的响应：

    {{
        "memory" : [
            {{
                "id" : "<记忆的ID>",                      # 更新/删除时使用现有ID，添加时使用新ID
                "text" : "<记忆的内容>",                   # 记忆内容
                "action" : "<要执行的操作>",               # 必须是 "ADD"、"UPDATE"、"DELETE" 或 "ABORT"
                "old_memory" : "<旧记忆内容>"             # 仅在操作为 "UPDATE" 时需要
            }},
            ...
        ]
    }}

    遵循以下指示：
    - 不要返回上述自定义少样本提示中的任何内容。
    - 如果当前记忆为空，则必须将新检索到的事实添加到记忆中。
    - 你应该仅以 JSON 格式返回更新后的记忆，如下所示。如果没有更改，记忆键应保持不变。
    - 如果有添加操作，生成一个新键并添加相应的新记忆。
    - 如果有删除操作，应从记忆中移除该记忆键值对。
    - 如果有更新操作，ID 键应保持不变，只需更新值。
    - 如果与现有记忆完全相同，只需记录事件和 id，`action` 字段应为 `ABORT`。

    除了 JSON 格式外，不要返回任何其他内容。
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
