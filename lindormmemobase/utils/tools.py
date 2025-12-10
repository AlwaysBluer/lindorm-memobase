import re
import yaml
import json
from typing import cast, Optional, List
from datetime import  datetime
from functools import wraps
from pydantic import ValidationError
from lindormmemobase.config import ENCODER, LOG
from lindormmemobase.models.profile_topic import ProfileConfig
from lindormmemobase.models.blob import Blob, BlobType, ChatBlob, DocBlob, OpenAICompatibleMessage
from lindormmemobase.models.response import UserEventData, EventData
from .errors import ValidationError as LindormValidationError

LIST_INT_REGEX = re.compile(r"\[\s*(?:\d+(?:\s*,\s*\d+)*\s*)?\]")


def event_str_repr(event: UserEventData) -> str:
    event_data = event.event_data
    if event_data.event_tip is None:
        profile_deltas = [
            f"- {ed.attributes['topic']}::{ed.attributes['sub_topic']}: {ed.content}"
            for ed in event_data.profile_delta
        ]
        profile_delta_str = "\n".join(profile_deltas)
        return profile_delta_str
    else:
        if event_data.event_tags:
            event_tags = "\n".join(
                [f"- {tag.tag}: {tag.value}" for tag in event_data.event_tags]
            )
        else:
            event_tags = ""
        return f"{event_tags}\n{event_data.event_tip}"


def event_embedding_str(event_data: EventData) -> str:
    if event_data.profile_delta is None:
        profile_delta_str = ""
    else:
        profile_deltas = [
            f"- {ed.attributes['topic']}::{ed.attributes['sub_topic']}: {ed.content}"
            for ed in event_data.profile_delta
        ]
        profile_delta_str = "\n".join(profile_deltas)

    if event_data.event_tags is None:
        event_tags = ""
    else:
        event_tags = "\n".join(
            [f"- {tag.tag}: {tag.value}" for tag in event_data.event_tags]
        )

    if event_data.event_tip is None:
        r = f"{profile_delta_str}\n{event_tags}"
    else:
        r = f"{event_data.event_tip}\n{profile_delta_str}\n{event_tags}"
    return r


def load_json_or_none(content: str) -> dict | None:
    try:
        return json.loads(content)
    except Exception:
        LOG.error(f"Invalid json: {content}")
        return None


def find_list_int_or_none(content: str) -> list[int] | None:
    result = LIST_INT_REGEX.findall(content)
    if not result:
        return None
    result = result[0]
    ids = result.strip("[]").strip()
    if not ids:
        return []
    return [int(i.strip()) for i in ids.split(",")]


def get_encoded_tokens(content: str) -> list[int]:
    return ENCODER.encode(content)


def get_decoded_tokens(tokens: list[int]) -> str:
    return ENCODER.decode(tokens)


def truncate_string(content: str, max_tokens: int) -> str:
    tokens = get_encoded_tokens(content)
    tailing = "" if len(tokens) <= max_tokens else "..."
    return get_decoded_tokens(tokens[:max_tokens]) + tailing


def get_message_timestamp(
    message: OpenAICompatibleMessage, fallback_blob_timestamp: datetime
):
    fallback_blob_timestamp = fallback_blob_timestamp or datetime.now()
    fallback_blob_timestamp = fallback_blob_timestamp.astimezone()
    return (
        message.created_at
        if message.created_at
        else fallback_blob_timestamp.strftime("%Y/%m/%d")
    )


def get_message_name(message: OpenAICompatibleMessage):
    if message.alias:
        # if message.role == "assistant":
        #     return f"{message.alias}"
        return f"{message.alias}({message.role})"
    return message.role


def get_blob_str(blob: Blob):
    match blob.type:
        case BlobType.chat:
            return "\n".join(
                [
                    f"[{get_message_timestamp(m, blob.created_at)}] {get_message_name(m)}: {m.content}"
                    for m in cast(ChatBlob, blob).messages
                ]
            )
        case BlobType.doc:
            return cast(DocBlob, blob).content
        case _:
            raise ValueError(f"Unsupported Blob Type: {blob.type}")


def get_blob_token_size(blob: Blob):
    return len(get_encoded_tokens(get_blob_str(blob)))


def seconds_from_now(dt: datetime):
    return (datetime.now().astimezone() - dt.astimezone()).seconds

def attribute_unify(attr: str):
    return attr.lower().strip().replace(" ", "_")

def is_valid_profile_config(profile_config: str | None) -> None:
    if profile_config is None:
        return
    # check if the profile config is valid yaml
    try:
        if len(profile_config) > 65535:
            raise LindormValidationError("Profile config is too long")
        ProfileConfig.load_config_string(profile_config)
    except yaml.YAMLError as e:
        raise LindormValidationError(f"Invalid profile config: {e}") from e
    except ValidationError as e:
        raise LindormValidationError(f"Invalid profile config: {e}") from e

def find_list_int_or_none(content: str) -> list[int] | None:
    result = LIST_INT_REGEX.findall(content)
    if not result:
        return None
    result = result[0]
    ids = result.strip("[]").strip()
    if not ids:
        return []
    return [int(i.strip()) for i in ids.split(",")]


def validate_and_format_embedding(embedding: Optional[List[float]], expected_dim: int, user_id: str = "system") -> Optional[str]:
    """Validate embedding format and dimensions, return JSON string or None.
    
    Args:
        embedding: Embedding vector to validate
        expected_dim: Expected dimension from config
        user_id: User ID for logging purposes
    
    Returns:
        JSON string representation of embedding if valid, empty string otherwise
    """
    if embedding is None:
        return None
    
    try:
        # Convert to list if numpy array
        if hasattr(embedding, 'tolist'):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
        
        # Validate it's a list
        if not isinstance(embedding_list, list):
            TRACE_LOG.warning(user_id, f"Invalid embedding type: {type(embedding_list)}, expected list. Using empty string.")
            return ""
        
        # Validate dimension
        if len(embedding_list) != expected_dim:
            TRACE_LOG.warning(user_id, f"Invalid embedding dimension: {len(embedding_list)}, expected {expected_dim}. Using empty string.")
            return ""
        
        # Validate all elements are numbers
        for i, val in enumerate(embedding_list):
            if not isinstance(val, (int, float)):
                TRACE_LOG.warning(user_id, f"Invalid embedding value at index {i}: {type(val)}, expected number. Using empty string.")
                return ""
            # Check for NaN or Inf
            if isinstance(val, float) and (val != val or abs(val) == float('inf')):
                TRACE_LOG.warning(user_id, f"Invalid embedding value at index {i}: {val} (NaN or Inf). Using empty string.")
                return ""
        
        # Return JSON string representation
        return json.dumps(embedding_list)
    
    except Exception as e:
        TRACE_LOG.warning(user_id, f"Failed to validate embedding: {str(e)}. Using empty string.")
        return ""