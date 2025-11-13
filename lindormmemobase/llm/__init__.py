from .openai_model_llm import openai_complete
from .lindormai_model_llm import lindormai_complete
# LLM provider factories
FACTORIES = {
    "openai": openai_complete,
    "lindormai": lindormai_complete,
}