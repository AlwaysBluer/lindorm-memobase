from . import zh_user_profile_topics
from lindormmemobase.models.response import AIUserProfiles
from .utils import pack_profiles_into_string
from lindormmemobase.config import Config

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

DEFAULT_JOB = """你负责从备忘录中提取用户画像，以结构化格式输出。
提取明确陈述或合理推断的事实和偏好。
使用与用户输入相同的语言记录。
"""

FACT_RETRIEVAL_PROMPT = """
{system_prompt}

## 任务
从下面的备忘录中提取与用户相关的事实和偏好。只关注用户自己的信息，不要提取其他人的信息。

## 输入说明

**主题建议：** 使用提供的主题/子主题列表作为参考。除非启用严格模式，否则可以创建新主题。

**已有的主题：** 当相同信息再次出现时，重用现有的主题/子主题名称。

**备忘录格式：** 你将收到用户备忘录（Markdown格式），由用户与助手的对话总结而成，包含用户信息、事件和偏好。

## 输出格式
按以下格式输出每一行：
```
- TOPIC{tab}SUB_TOPIC{tab}MEMO
```

每行包含：
- **TOPIC**：信息类别（如：基本信息、工作、兴趣）
- **SUB_TOPIC**：具体子类别（如：姓名、职位、爱好）
- **MEMO**：提取的用户事实/偏好

元素用 `{tab}` 分隔，每行以 `- ` 开头，用换行符分隔。

## 示例
{examples}

## 严格规则
- **只输出画像行**（不要输出思考过程、解释或其他文字）
- 仅提取有实际值的事实；无值则跳过
- **推断隐含信息**，不仅限于明确陈述
- 将同一主题/子主题的所有内容合并到一行（不重复）
- **时间处理：**
  - 使用具体日期（YYYY/MM/DD），禁用相对时间（"今天"、"昨天"）
  - 区分提及时间与事件时间：`[提及于 YYYY/MM/DD, 发生于 YYYY/MM/DD]`
  - 如用户提到时间敏感信息，推断具体日期
- 未找到相关信息时返回空列表
- **语言匹配：** 用与用户输入相同的语言记录事实
- **只关注用户：** 不要提取他人信息（例如备忘录说"张三是经理"，不要创建 work{tab}职位，除非是关于用户的）
- {strict_topic_prompt}

## 可用主题
{topic_examples}

现在从下面的备忘录中提取画像。
"""


def get_strict_topic_prompt(strict_mode: bool = True):
    if strict_mode:
        return "请务必严格按照给定的主题/子主题给出答案，禁止自己创建主题/子主题"
    else:
        return "如果你认为有必要，可以创建自己的主题/子主题"


def pack_input(already_input, chat_strs, strict_mode: bool = True):
    header = ""
    if strict_mode:
        header = "**严格模式**：只能使用主题建议中的主题/子主题。创建新主题将导致回答无效。"
    return f"""{header}

**已有的主题：**
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
