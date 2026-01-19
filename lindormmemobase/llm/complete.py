import time
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from typing import Type, TypeVar

from lindormmemobase.config import LOG
from lindormmemobase.utils.errors import LLMError
from lindormmemobase.core.extraction.prompts.utils import convert_response_to_json
from . import FACTORIES

T = TypeVar('T', bound=object)

# Retryable network errors: connection issues, timeout, gzip decode errors
RETRYABLE_ERRORS = (
    httpx.DecodingError,
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    before_sleep=before_sleep_log(LOG, LOG.level),
)
async def llm_complete(
    prompt,
    system_prompt=None,
    history_messages=[],
    json_mode=False,
    model=None,
    max_tokens=1024,
    config=None,
    **kwargs,
) -> str | dict:
    if config is None:
        raise ValueError("config parameter is required")

    use_model = model or config.best_llm_model
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        start_time = time.time()
        results = await FACTORIES[config.llm_style](
            use_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            max_tokens=max_tokens,
            config=config,
            **kwargs,
        )
        latency = (time.time() - start_time) * 1000
    except Exception as e:
        LOG.error(f"Error in llm_complete: {e}")
        raise LLMError(f"Error in llm_complete: {e}") from e

    if not json_mode:
        return results
    parse_dict = convert_response_to_json(results)
    if parse_dict is not None:
        return parse_dict
    else:
        raise LLMError("Failed to parse JSON response")


async def llm_stream_complete(
    prompt,
    system_prompt=None,
    history_messages=[],
    model=None,
    max_tokens=1024,
    config=None,
    **kwargs,
):
    """Stream completion from LLM."""
    if config is None:
        raise ValueError("config parameter is required")
    
    use_model = model or config.best_llm_model
    
    try:
        # Import the streaming function based on llm_style
        if config.llm_style == "openai":
            from .openai_model_llm import openai_stream_complete
            stream_func = openai_stream_complete
        elif config.llm_style == "lindormai":
            from .lindormai_model_llm import lindormai_stream_complete
            stream_func = lindormai_stream_complete
        else:
            raise ValueError(f"Streaming not supported for llm_style: {config.llm_style}")
        
        async for chunk in stream_func(
            use_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            max_tokens=max_tokens,
            config=config,
            **kwargs,
        ):
            yield chunk
            
    except Exception as e:
        LOG.error(f"Error in llm_stream_complete: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    before_sleep=before_sleep_log(LOG, LOG.level),
)
async def llm_complete_with_schema(
    prompt: str,
    response_model: Type[T],
    system_prompt: str | None = None,
    history_messages: list = [],
    model: str | None = None,
    max_tokens: int = 1024,
    config=None,
    **kwargs,
) -> T:
    """LLM completion with Pydantic response model validation.

    Uses JSON Mode (response_format={"type": "json_object"}) and validates
    the response against a Pydantic model for type safety and structure.

    Args:
        prompt: User prompt
        response_model: Pydantic model class for response validation
        system_prompt: Optional system prompt
        history_messages: Optional chat history
        model: Model name (uses config.best_llm_model if None)
        max_tokens: Max tokens in response
        config: System configuration (required)
        **kwargs: Additional LLM parameters

    Returns:
        Validated Pydantic model instance

    Raises:
        ValueError: If config is None
        LLMError: If LLM call fails or response validation fails
    """
    if config is None:
        raise ValueError("config parameter is required")

    use_model = model or config.best_llm_model

    # Enable JSON mode
    kwargs["response_format"] = {"type": "json_object"}
    kwargs["json_mode"] = True

    # Call LLM
    try:
        response_str = await llm_complete(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            model=use_model,
            max_tokens=max_tokens,
            config=config,
            **kwargs,
        )
    except Exception as e:
        raise LLMError(f"LLM call failed: {e}") from e

    # Validate response with Pydantic
    # When json_mode=True, llm_complete returns dict; when False, returns str
    try:
        if isinstance(response_str, dict):
            # LLM already parsed JSON, validate dict directly
            return response_model.model_validate(response_str)
        else:
            # LLM returned raw JSON string, parse it
            return response_model.model_validate_json(response_str)
    except Exception as e:
        LOG.error(f"Response validation failed: {e}\nRaw response: {response_str}")
        raise LLMError(f"Response validation failed: {e}") from e