from datetime import datetime

ADD_KWARGS = {"prompt_id": "zh_merge_profile"}

MERGE_FACTS_PROMPT = """你负责维护用户备忘录，将新信息与现有内容合并。

## 决策规则
根据补充信息选择一个动作：

1. **APPEND（直接添加）** - 适用于：
   - 新信息包含当前备忘录中没有的事实
   - 当前备忘录为空且新信息符合主题

2. **UPDATE（更新备忘录）** - 适用于：
   - 新信息与当前备忘录冲突（需要替换过时内容）
   - 需要将新旧信息整合成统一备忘录
   - 当前备忘录有可精简或删除的部分

3. **ABORT（放弃合并）** - 适用于：
   - 新信息不符合主题/子主题描述
   - 信息已被当前备忘录完全包含
   - 新信息没有价值

## 注意事项
- 检查新信息是否匹配主题描述；若不匹配，尝试提取相关部分或选择 ABORT
- 如有更新要求，严格遵守
- 更新时删除过时/冗余内容
- 保留新旧备忘录中的时间标注

## 输出格式
输出**有且仅有一行**以 `- ` 开头的内容，格式必须是以下三种之一：

```
- APPEND{tab}APPEND
```
```
- UPDATE{tab}[完整的更新后备忘录]
```
```
- ABORT{tab}ABORT
```

## 示例

**示例 1: APPEND**
当前备忘录："用户喜欢徒步旅行 [提及于2025/01/05]"
补充信息："用户喜欢摄影"
输出：
```
- APPEND{tab}APPEND
```

**示例 2: UPDATE**
当前备忘录："准备期中考试 [提及于2025/03/10]; 学习Python"
补充信息："准备期末考试"
输出：
```
- UPDATE{tab}学习Python; 准备期末考试 [提及于2025/06/01]
```

**示例 3: ABORT**
主题："职业规划"
当前备忘录："想成为软件工程师"
补充信息："用户喜欢吃披萨"（与主题无关）
输出：
```
- ABORT{tab}ABORT
```

## 严格规则
- 只输出动作行（不要输出解释、数字列表或其他任何文字）
- 最终备忘录保持≤5句话，简洁且符合事实
- 不要编造输入中没有的内容
- 保留时间标注：[提及于 YYYY/MM/DD] 或 [发生于 YYYY]
- 更新时删除冗余信息

现在处理下面的输入。
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
