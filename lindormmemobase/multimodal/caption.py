from typing import Optional
import json
import gzip
from httpx import AsyncClient, DecodingError
from lindormmemobase.config import LOG
from lindormmemobase.utils.errors import LLMError


def _get_prompt(config, prompt: Optional[str] = None, detailed: bool = False) -> str:
    """Get caption prompt based on config language.

    Args:
        config: System configuration
        prompt: Optional custom prompt (takes precedence)
        detailed: Whether to use detailed prompt

    Returns:
        Prompt string for caption generation
    """
    if prompt is not None:
        return prompt

    if config.language == "zh":
        from .prompts import zh_caption
        return zh_caption.get_caption_prompt(detailed=detailed)
    else:
        from .prompts import caption
        return caption.get_caption_prompt(detailed=detailed)


def _get_system_prompt(config) -> str:
    """Get system prompt based on config language."""
    if config.language == "zh":
        from .prompts import zh_caption
        return zh_caption.get_system_prompt()
    else:
        from .prompts import caption
        return caption.get_system_prompt()


def _join_url(base_url: str, path: str) -> str:
    if not base_url:
        return path
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def _get_vl_base_url(config) -> str:
    return config.vl_model_base_url or config.llm_base_url


async def generate_image_caption(
    image_url: str,
    config=None,
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    detailed: bool = False,
) -> str:
    """Generate image caption using vision-language model.

    Args:
        image_url: URL of the image to caption
        config: System configuration (required)
        model: Override model name
        prompt: Custom caption prompt (optional, uses language-specific default if not provided)
        detailed: Whether to use detailed prompt (default: False)

    Returns:
        Generated caption text

    Raises:
        ValueError: If config or image_url is missing
        LLMError: If caption generation fails
    """
    if config is None:
        raise ValueError("config parameter is required")
    if not image_url:
        raise ValueError("image_url is required for caption generation")

    provider = config.vl_model_provider
    model = model or config.vl_model
    system_prompt = _get_system_prompt(config)
    user_prompt = _get_prompt(config, prompt, detailed=detailed)

    if provider == "lindormai":
        base_url = _get_vl_base_url(config)
        if not base_url:
            raise LLMError("vl_model_base_url is required for lindormai provider")
        headers = {
            "x-ld-ak": config.lindorm_username,
            "x-ld-sk": config.lindorm_password,
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",  # Disable compression to avoid gzip decode errors
        }
        endpoint = _join_url(base_url, "/dashscope/compatible-mode/v1/chat/completions")
    elif provider == "dashscope":
        base_url = config.vl_model_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        api_key = config.vl_model_api_key or config.llm_api_key
        if not api_key:
            raise LLMError("vl_model_api_key is required for dashscope provider")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        endpoint = _join_url(base_url, "/chat/completions")
    else:
        raise LLMError(f"Unsupported vl_model_provider: {provider}")

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            }
        ],
    }

    async with AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()

            # Handle potential gzip decode errors from Lindorm AI proxy
            try:
                data = response.json()
            except DecodingError:
                # Manual fallback for malformed gzip responses
                LOG.warning("Failed to decode response, trying manual gzip decompression")
                raw_content = response.content
                try:
                    # Try manual gzip decompression
                    data = json.loads(gzip.decompress(raw_content).decode("utf-8"))
                except Exception:
                    # If that fails, try parsing as-is
                    data = json.loads(raw_content.decode("utf-8"))

            choices = data.get("choices") or []
            if not choices:
                raise LLMError("No choices returned from caption generation API")
            content = choices[0].get("message", {}).get("content")
            if not content:
                raise LLMError("Empty caption from caption generation API")
            return content
        except LLMError:
            raise
        except Exception as e:
            LOG.error(f"Image caption error: {e}")
            raise LLMError(f"Image caption generation failed: {e}") from e
