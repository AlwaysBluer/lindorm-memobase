from typing import Optional
import json
import gzip
from httpx import AsyncClient, DecodingError
from lindormmemobase.config import LOG
from lindormmemobase.utils.errors import LLMError


DEFAULT_CAPTION_PROMPT = (
    "Describe the image in a single concise paragraph. Focus on observable objects, "
    "people, actions, and the scene. Avoid speculation or sensitive inferences."
)


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
) -> str:
    if config is None:
        raise ValueError("config parameter is required")
    if not image_url:
        raise ValueError("image_url is required for caption generation")

    provider = config.vl_model_provider
    model = model or config.vl_model
    prompt = prompt or DEFAULT_CAPTION_PROMPT

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
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                    {
                        "type": "text",
                        "text": prompt,
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
