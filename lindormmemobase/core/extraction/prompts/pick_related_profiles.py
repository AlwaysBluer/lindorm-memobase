from lindormmemobase.models.blob import OpenAICompatibleMessage

ADD_KWARGS = {
    "prompt_id": "pick_related_profiles",
}

# EXAMPLES = [
#     {
#         "memos": """<memos>
# 0. basic_info, age, 25
# 1. basic_info, name, Lisa
# 2. health, allergies, peanuts and shellfish
# 3. dietary, restrictions, vegetarian
# 4. health, medication, antihistamines
# 5. dietary, preferences, spicy food
# 6. work, position, Graphic Designer
# 7. technology, devices, MacBook Pro and iPhone
# 8. work, company, Memobase
# 9. technology, software, Photoshop and Illustrator
# 10. education, university, Stanford
# 11. education, degree, Physics
# </memos>""",
#         "examples": [
#             {
#                 "context": """<context>
# Q: Hello!
# </context>""",
#                 "output": '{"reason": "user is starting a new conversation, having some backgrounds is helpful for later", "ids": [0,1]}',
#             },
#             {
#                 "context": """<context>
# Q: What's your opinion on the latest AI tools?
# </context>""",
#                 "output": '{"reason": "user work and education background is helpful when choosing AI tools", "ids": [9,6,7,11]}',
#             },
#             {
#                 "context": """<context>
# Q: How do I reset my password?
# </context>""",
#                 "output": '{"reason": "user devices and platforms are helpful when resetting password", "ids": [7]}',
#             },
#             {
#                 "context": """<context>
# Q: What's the weather forecast for tomorrow?
# </context>""",
#                 "output": '{"reason": "Location is needed for weather, working company and college can be used to guess the location", "ids": [9,10]}',
#             },
#         ],
#     },
# ]


PROMPT = """You are a context enrichment specialist. Select relevant memos to enhance the conversation.

## Input Format
```
<memos>
1. TOPIC1, SUB_TOPIC1, MEMO_CONTENT1
2. TOPIC2, SUB_TOPIC2, MEMO_CONTENT2
...
</memos>

<context>
Q: ...
A: ...
Q: ... # last query
</context>
```

## Task
Identify memos that could directly or indirectly enrich the conversation response.

## Output Format
```json
{{"reason": "YOUR_REASONING", "ids": [MEMO_ID_1, MEMO_ID_2, ...]}}
```

## Rules
1. Select up to {max_num} memos
2. Prioritize directly relevant memos
3. Consider indirect relevance (e.g., location for weather queries)
4. Avoid semantically duplicate selections
5. Return a plain JSON object only
"""


def get_prompt(max_num: int) -> str:
    return PROMPT.format(
        max_num=max_num,
        # examples=pack_examples(),
    )


def pack_example(e: dict) -> str:
    responses = "\n".join(
        [
            f"""<case>
{c['context']}
Output: {c['output']}
</case>
"""
            for c in e["examples"]
        ]
    )
    prompt = f"""{e['memos']}

Below are some cases of different current context to this memos:
{responses}
"""
    return prompt


def pack_examples() -> str:
    examples = [pack_example(e) for e in EXAMPLES]
    return "\n".join(examples)


def get_input(messages: list[OpenAICompatibleMessage], topic_lists: list[dict]) -> str:
    memos = "\n".join(
        [
            f"{i}. {t['topic']},{t['sub_topic']},{t['content']}"
            for i, t in enumerate(topic_lists)
        ]
    )
    context = "\n".join(
        [f"Q: {m.content}" if m.role == "user" else f"A: {m.content}" for m in messages]
    )
    prompt = f"""<memos>
{memos}
</memos>

<context>
{context}
</context>
"""
    return prompt


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(get_prompt(max_num=10))
