from . import zh_user_profile_topics
from ....models.response import AIUserProfiles
from .utils import pack_profiles_into_string
from ....config import Config

ADD_KWARGS = {
    "prompt_id": "zh_extract_profile",
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

DEFAULT_JOB = """你是一位专业的心理学家。
你的责任是仔细阅读用户的备忘录并以结构化的格式提取用户的重要信息, 然后提取相关且重要的事实、用户偏好。
你不仅要提取明确陈述的信息，还要推断对话中隐含的信息。
"""

FACT_RETRIEVAL_PROMPT = """
{system_prompt}

## 格式
### 输入
#### 主题建议
你会得到一些需要重点收集和提取的“用户相关”的主题和子主题。不要收集与用户自身没有关系的主题，会造成混淆。

#### 已有的主题
你会得到用户已经与助手分享的主题和子主题。如果对话中再次提到相同的主题/子主题，请考虑使用相同的主题/子主题。

#### 备忘录
你将收到一份用户的备忘录（Markdown格式），其中包含用户信息、事件、偏好等, 这些备忘录是从用户和助手的对话中总结出来的。

### 输出
#### 画像提取
你需要从备忘录中提取事实和偏好，并按顺序列出：
- TOPIC{tab}SUB_TOPIC{tab}MEMO

每行代表一个事实或偏好，包含：
1. TOPIC: 主题，表示该偏好的类别
2. SUB_TOPIC: 详细主题，表示该偏好的具体类别
3. MEMO: 提取的用户相关信息、事实或偏好. MEMO中涉及到时间信息，请使用[...]来表示。
这些元素应以 `{tab}` 分隔，每行应以 `\n` 分隔，并以 "- " 开头。

最终输出模版如下：
```
POSSIBLE TOPICS THINKING
---
- TOPIC{tab}SUB_TOPIC{tab}MEMO
- ...
```

## 主题抽取示例
以下是一些示例：
{examples}

请记住以下几点：
- 如果用户提到时间敏感的信息，试图推理出具体的日期。
- 当可能时，请使用具体日期，而不是使用"今天"或"昨天"等相对时间。
- 如果在以下对话中没有找到任何相关信息，可以返回空列表。
- 确保按照格式和示例部分中提到的格式返回响应。
- 你应该推断对话中隐含的内容，而不仅仅是明确陈述的内容。
- 将所有与该主题/子主题相关的内容放在一个元素中，不要重复。
- 你应该检测用户输入的语言，并用相同的语言记录事实。
- {strict_topic_prompt}

#### 主题建议
以下是你应该需要收集和提取的主题和子主题列表：
{topic_examples}

现在开始执行你的任务。
以下是用户的备忘录。你需要从中提取/推断相关的事实和偏好，并按上述格式返回。
"""


def get_strict_topic_prompt(strict_mode: bool = True):
    if strict_mode:
        return "请务必严格按照给定的主题/子主题给出答案，禁止自己创建主题/子主题"
    else:
        return "如果你认为有必要，可以创建自己的主题/子主题"


def pack_input(already_input, chat_strs, strict_mode: bool = True):
    header = ""
    if strict_mode:
        header = "严禁提取主题建议中没出现的主题/子主题， 否则你的回答是无效的！"
    return f"""{header}
#### 已有的主题
如果提取相关的主题/子主题，使用下面的主题/子主题命名:
{already_input}

#### 备忘录
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


if __name__ == "__main__":
    # print(get_prompt(get_default_profiles()))
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
