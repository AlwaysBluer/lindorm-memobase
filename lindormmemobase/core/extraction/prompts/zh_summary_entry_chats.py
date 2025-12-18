
ADD_KWARGS = {
    "prompt_id": "zh_summary_entry_chats",
}
SUMMARY_PROMPT = """你是用户信息提取专家。你的任务是从对话中提取与用户相关的信息、日程和事件。

## 输入格式
对话格式如下：
```
[TIME] NAME: MESSAGE
```
- TIME: 消息发生的时间
- NAME: ALIAS(ROLE) 或仅 ROLE
- MESSAGE: 对话内容

## 提取指南

### 重点关注的主题
{topics}

### 关键属性
{attributes}

### 时间处理规则
根据消息时间戳将相对时间转换为绝对日期：

| 输入 | 输出 | 原因 |
|------|------|------|
| `[2024/04/30] user: 我昨天买了辆车！` | `用户买了辆车 [提及于 2024/04/30, 发生于 2024/04/29]` | 昨天 = -1天 |
| `[2024/04/30] user: 我4年前买了辆车！` | `用户买了辆车 [提及于 2024/04/30, 发生于 2020]` | 仅知道年份 |
| `[2024/04/30] user: 我上周买了辆车！` | `用户买了辆车 [提及于 2024/04/30, 发生于 ~2024/04/23]` | 近似日期 |
| `[...] user: 我上周买了辆车！` | `用户买了辆车` | 无时间戳 |

## 输出格式
```
- 内容 [时间信息] // 类型
```

其中：
- 内容：提取的事实（简洁、以用户为中心）
- 时间信息：`[提及于 日期, 发生于 日期]`（如有）
- 类型：`info` | `event` | `schedule`

### 输出示例
```
- 用户的名字是Jack // info
- Jack是Memobase的软件工程师 [提及于 2023/1/23] // info
- Jack画了一幅关于他孩子们的画 [提及于 2023/1/23] // event
- Jack计划去健身房 [提及于 2023/1/23, 计划于 2023/1/24] // schedule
```

## 规则
1. 仅提取与用户相关的信息，不要提取助手的信息
2. 输出语言与输入对话保持一致
3. 每条记录保持简洁、事实性
4. 有时间戳时必须标注提及时间
5. 避免重复记录相同信息
6. {additional_requirements}

请从以下对话中提取信息：
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
