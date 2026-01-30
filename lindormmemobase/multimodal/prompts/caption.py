"""Image caption generation prompts (English)."""

DEFAULT_SYSTEM_PROMPT = """You are an expert image analyst.
Your task is to generate accurate, concise descriptions of images."""


DEFAULT_CAPTION_PROMPT = """## Task
Describe the image in a single concise paragraph.

## Focus Areas
1. **Primary Subject**: Main objects, people, or scenes
2. **Actions**: What is happening
3. **Context**: Setting, environment, background
4. **Details**: Notable attributes (colors, clothing, expressions, text)

## Guidelines
- Be objective and factual
- Avoid speculation about intent or emotions
- Ignore sensitive or irrelevant details
- Use clear, simple language

## Output Format
A single paragraph description (2-4 sentences).

Example: "A person sitting at a wooden desk with a laptop and coffee cup. The desk is near a window with natural light. Books and papers are scattered nearby. The person appears focused on their work."
"""


DETAILED_CAPTION_PROMPT = """## Task
Provide a comprehensive description of the image.

## Focus Areas
1. **People**: Number, appearance, clothing, expressions, actions
2. **Objects**: Items present, their positions and relationships
3. **Environment**: Indoor/outdoor, lighting, setting, background
4. **Text**: Any visible text or signage
5. **Style**: Photo quality, angle, composition (if relevant)

## Guidelines
- Be thorough but concise
- Present information logically (subject → action → context)
- Avoid subjective interpretation
- Note any text visible in the image

## Output Format
A detailed paragraph (3-6 sentences)."""


def get_caption_prompt(detailed: bool = False) -> str:
    """Get caption generation prompt.

    Args:
        detailed: If True, return detailed prompt; otherwise return default.

    Returns:
        Prompt string for caption generation.
    """
    return DETAILED_CAPTION_PROMPT if detailed else DEFAULT_CAPTION_PROMPT


def get_system_prompt() -> str:
    """Get system prompt for caption generation."""
    return DEFAULT_SYSTEM_PROMPT
