from .openai_model_llm import openai_complete

# LLM provider factories
FACTORIES = {
    "openai": openai_complete,
    "doubao_cache": openai_complete,  # Use same function for now
}