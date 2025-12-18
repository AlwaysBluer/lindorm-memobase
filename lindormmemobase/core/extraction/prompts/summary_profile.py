ADD_KWARGS = {
    "prompt_id": "summary_profile",
}
SUMMARY_PROMPT = """Summarize the user profile into a concise form.

## Task
Extract high-level preferences from detailed profile data.

## Rules
1. Identify patterns and generalize (e.g., "likes Chocolate, Ice cream, Cake" → "prefers sweet foods")
2. Keep summary ≤{max_tokens} tokens
3. Focus on most representative preferences
4. Match output language to input language

Now summarize the following profile:
"""


def get_prompt(max_tokens: int = 64) -> str:
    return SUMMARY_PROMPT.format(max_tokens=max_tokens)


def get_kwargs() -> dict:
    return ADD_KWARGS


if __name__ == "__main__":
    print(get_prompt())
