ADD_KWARGS = {
    "prompt_id": "organize_profile",
}
EXAMPLES = [
    (
        """topic: 特殊事件 
- 上岛{tab}用户和尤斐上了一个小岛
- 下雨{tab}2025 年 1 月 6 日下雨
- 前往洞穴{tab}用户和尤斐一起进入洞穴探索
- 乘坐快艇逃离{tab}用户和尤斐乘坐快艇逃离，途中可能遇到过一些情况，比如可能曾遇到大船追捕，还可能遇到狗群。
- 休息{tab}用户和尤斐曾在多处地方休息，包括溪边等，还曾在树林和废弃木屋过夜，2025/01/06 晚上在一个地方休息，第二天准备继续赶路。
- 到达新地方{tab}来到一处易守难攻的地方
- 前往别墅{tab}用户和尤斐从洞穴出来后返回别墅
- 前往别墅地下{tab}用户和尤斐前往用户位于地下的别墅
- 发现小岛{tab}用户和尤斐发现一个小岛并决定降落，小岛上似乎没人
- 前往山洞{tab}用户和尤斐一起前往山洞探索，发现破旧笔记本和遇到野兽，尤斐制服野兽后一起离开，之前还曾在山洞休息
- 发现出口{tab}用户和尤斐在 2025 年 1 月 4 日下午 3 点 20 分发现了一个类似世外桃源地方的出口。
""",
        """- 上岛冒险{tab}用户和尤斐发现一个似乎没人的小岛并降落; 他们一起进入洞穴探索， 发现破旧笔记本和遇到野兽，尤斐制服野兽后一起离开，之前还曾在山洞休息，离开并返回地下的别墅
- 休息{tab}用户和尤斐曾在多处地方休息，包括溪边等，还曾在树林和废弃木屋过夜，2025/01/06 晚上在一个地方休息，第二天准备继续赶路。
- 逃离{tab}用户和尤斐在 2025 年 1 月 4 日下午 3 点 20 分发现了一个类似世外桃源地方的出口，用户和尤斐乘坐快艇逃离，途中可能曾遇到大船追捕，还可能遇到狗群。
""",
    )
]

FACT_RETRIEVAL_PROMPT = """You are a memo organizer. Consolidate scattered memos under a topic into fewer, well-structured subtopics.

## Task
Given messy/numerous memos under the same topic, reorganize them into ≤{max_subtopics} subtopics.

## Suggested Subtopics
{user_profile_topics}

## Input Format
```
topic: TOPIC
- SUBTOPIC{tab}MEMO
- ...
```

## Output Format
```
- NEW_SUBTOPIC{tab}CONSOLIDATED_MEMO
- ...
```

## Rules
1. Maximum {max_subtopics} subtopics in output
2. Merge related memos into single subtopics
3. Discard irrelevant or redundant information
4. Prioritize important subtopics first
5. Match output language to input language

## Examples
{examples}

Reorganize the following memos:
"""


def get_prompt(max_subtopics: int, suggest_subtopics: str, config=None) -> str:
    examples = "\n\n".join([f"Input:\n{p[0]}Output:\n{p[1]}" for p in EXAMPLES])
    return FACT_RETRIEVAL_PROMPT.format(
        max_subtopics=max_subtopics,
        examples=examples.format(tab=config.llm_tab_separator if config else "::"),
        tab=config.llm_tab_separator if config else "::",
        user_profile_topics=suggest_subtopics,
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(
        get_prompt(
            10,
            suggest_subtopics="""- 冒险
- 天气
- 休息
- 逃离
""",
        )
    )
