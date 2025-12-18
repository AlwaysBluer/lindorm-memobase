from datetime import datetime

ADD_KWARGS = {"prompt_id": "zh_merge_profile"}


MERGE_FACTS_PROMPT = """你是备忘录维护专家。你的任务是将新信息与现有用户备忘录合并。

## 决策框架

分析新信息并决定执行一个操作：

| 操作 | 使用场景 |
|------|----------|
| **APPEND** | 新信息有价值且不与现有备忘录冲突 |
| **UPDATE** | 新信息与现有备忘录冲突或需要整合 |
| **ABORT** | 新信息重复、无关或不符合主题要求 |

## 决策流程

1. **主题相关性**：新信息是否符合备忘录的主题/子主题？
   - 如果不符合：能否调整？若不能 → ABORT
2. **价值判断**：新信息是否增加有意义的内容？
   - 如果没有（重复/空白）→ ABORT
3. **冲突检查**：是否与现有备忘录冲突？
   - 是 → UPDATE（重写完整备忘录）
   - 否 → APPEND

## 输出格式

仅输出一行，格式如下：
```
- 操作{tab}内容
```

其中：
- `APPEND` → `- APPEND{tab}APPEND`
- `ABORT` → `- ABORT{tab}ABORT`
- `UPDATE` → `- UPDATE{tab}[重写后的完整备忘录]`

## 规则
1. 备忘录保持简洁，不超过5句话
2. 保留时间标注：`[提及于 日期, 发生于 日期]`
3. 不编造输入中未提及的内容
4. 更新时去除冗余（如："用户很伤心; 用户心情不好" → "用户很伤心"）
5. 仅输出操作行，不输出其他以 "- " 开头的内容

示例：
```
- UPDATE{tab}使用多邻国自学日语，目标通过N2 [提及于 2025/05/05]；准备期末考试 [提及于 2025/06/01]
```

现在执行任务。
"""


def get_input(
    topic, subtopic, old_memo, new_memo, update_instruction=None, topic_description=None, config=None
):
    today = datetime.now().strftime("%Y-%m-%d") if config is None else datetime.now().astimezone(config.timezone).strftime("%Y-%m-%d")
    return f"""今天是{today}。
## 备忘录更新要求
{update_instruction or "[empty]"}
### 备忘录主题描述
{topic_description or "[empty]"}
## 备忘录主题
{topic}, {subtopic}
## 当前备忘录
{old_memo or "[empty]"}
## 补充信息
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
