from . import zh_user_profile_topics
from lindormmemobase.models.response import AIUserProfiles
from .utils import pack_profiles_into_string
from lindormmemobase.config import Config

ADD_KWARGS = {
    "prompt_id": "zh_extract_profile",
    "max_tokens": 4096,
}

EXAMPLES = [
    (
        """
- 用户向助手问好。

主题/子主题:
topic: "基本信息"
  sub_topics:
    - name: "姓名"
    - name: "年龄"
    - name: "性别"
""",
        AIUserProfiles(**{"facts": []}),
    ),
    (
        """
- 用户是MemoBase的软件工程师 [提及于2025/01/01]
- 用户的名字是John [提及于2025/01/01]

主题/子主题:
topic: "基本信息"
  sub_topics:
    - "姓名"
    - "年龄"
    - "性别"
topic: "工作"
  sub_topics:
    - "公司"
    - "时间"
    
""",
        AIUserProfiles(
            **{
                "facts": [
                    {
                        "topic": "基本信息",
                        "sub_topic": "姓名",
                        "memo": "John",
                    },
                    {
                        "topic": "基本信息",
                        "sub_topic": "职业",
                        "memo": "用户是软件工程师 [提及于2025/01/01]",
                    },
                    {
                        "topic": "工作",
                        "sub_topic": "公司",
                        "memo": "用户在MemoBase工作 [提及于2025/01/01]",
                    },
                ]
            }
        ),
    )
]


DEFAULT_JOB = """你是用户画像提取专家。
你的任务是从用户备忘录中提取结构化的画像信息。
同时提取明确陈述的事实和合理推断的信息。
"""

FACT_RETRIEVAL_PROMPT = """{system_prompt}

## 任务概述
从备忘录中提取与用户相关的事实和偏好，形成结构化画像。

## 可用主题
以下是推荐的提取主题/子主题：
{topic_examples}

## 输出格式

### 第一步：分析
简要识别备忘录中提及或可推断的主题/子主题。

### 第二步：提取
将每个事实输出为 markdown 列表项：
```
- 主题{tab}子主题{tab}内容
```

示例：
```
- 基本信息{tab}姓名{tab}张三
- 工作{tab}职位{tab}在MemoBase担任软件工程师 [提及于 2025/01/01]
```

## 提取规则
1. **以用户为中心**：仅提取关于用户本人的信息，不提取他人信息
2. **时间处理**：保留时间标注 `[提及于 日期, 发生于 日期]`
3. **去重整合**：将相关事实整合到同一主题/子主题下
4. **合理推断**：提取隐含信息（如：多部诺兰电影 → 喜欢诺兰）
5. **完整性**：包含所有相关事实，但不编造
6. {strict_topic_prompt}

## 示例
{examples}

请从以下备忘录中提取画像信息：
"""


def get_strict_topic_prompt(strict_mode: bool = True):
    if strict_mode:
        return "**主题约束**：严格按照给定的主题/子主题提取，禁止自创主题"
    else:
        return "如果你认为有必要，可以创建自己的主题/子主题"


def pack_input(already_input, chat_strs, strict_mode: bool = True):
    header = ""
    if strict_mode:
        header = "严禁提取主题建议中没出现的主题/子主题，否则你的回答无效！\n"
    return f"""{header}#### 已有的主题
如果提取相关的主题/子主题，使用下面的主题/子主题命名:
{already_input}

**备忘录：**
{chat_strs}
"""


def get_default_profiles() -> str:
    return zh_user_profile_topics.get_prompt()


def get_prompt(topic_examples: str, config: Config) -> str:
    sys_prompt = config.system_prompt or DEFAULT_JOB
    examples = "\n\n".join(
        [
            f"""<example>
<input>{p[0]}</input>
<output>
{pack_profiles_into_string(p[1])}
</output>
</example>
"""
            for p in EXAMPLES
        ]
    )
    return FACT_RETRIEVAL_PROMPT.format(
        system_prompt=sys_prompt,
        examples=examples,
        tab=config.llm_tab_separator,
        topic_examples=topic_examples,
        strict_topic_prompt=get_strict_topic_prompt(config.profile_strict_mode),
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


def get_prompt_json_mode(topic_examples: str, config: Config) -> str:
    """获取 JSON Mode 提示词（用于 extract_profile）。

    返回一个指示 LLM 仅输出 JSON 的提示词，
    与 response_format={"type": "json_object"} 兼容。
    """
    sys_prompt = config.system_prompt or DEFAULT_JOB
    return f"""{sys_prompt}

## 任务概述
从备忘录中提取与用户相关的事实和偏好，形成结构化画像。

## 可用主题
以下是推荐的提取主题/子主题：
{topic_examples}

## 输出格式

仅返回 JSON 对象（不包含 markdown、不包含解释文字）：
```json
{{
  "facts": [
    {{"topic": "基本信息", "sub_topic": "姓名", "memo": "张三"}},
    {{"topic": "工作", "sub_topic": "职位", "memo": "软件工程师 [提及于 2025/01/01]"}}
  ]
}}
```

## 重要规则
1. 仅返回 JSON 对象，不要包含任何其他文字
2. 如果没有找到相关信息，facts 数组可以为空
3. 每个 fact 必须包含 3 个字段：topic, sub_topic, memo
4. topic 和 sub_topic 使用下划线命名法
5. 保留时间标注：[提及于 日期, 发生于 日期]
6. 同时提取明确陈述的事实和合理推断的信息
7. 仅提取关于用户本人的信息，不提取他人信息
8. 匹配用户输入的语言

## 示例

输入："用户与思蕾结婚 [提及于2025/01/15，发生于2025/01/01]"
输出：{{"facts": [
  {{"topic": "demographics", "sub_topic": "marital_status", "memo": "已婚"}},
  {{"topic": "life_event", "sub_topic": "Marriage", "memo": "与思蕾结婚 [提及于2025/01/15，婚礼于2025/01/01]"}}
]}}

输入："用户向助手问好。"
输出：{{"facts": []}}
"""


if __name__ == "__main__":
    examples = "\n\n".join(
        [
            f"""<example>
    <input>{p[0]}</input>
    <output>
    {pack_profiles_into_string(p[1])}
    </output>
    </example>
    """
            for p in EXAMPLES
        ]
    )
    print(examples)
