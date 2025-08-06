from .import (
    user_profile_topics,
    extract_profile,
    merge_profile,
    organize_profile,
    summary_entry_chats,
    zh_user_profile_topics,
    zh_extract_profile,
    zh_merge_profile,
    zh_summary_entry_chats,
)
from ....models.types import UpdateResponse



PROMPTS = {
    "en": {
        "entry_summary": summary_entry_chats,
        "profile": user_profile_topics,
        "extract": extract_profile,
        "merge": merge_profile,
        "organize": organize_profile,
    },
    "zh": {
        "entry_summary": zh_summary_entry_chats,
        "profile": zh_user_profile_topics,
        "extract": zh_extract_profile,
        "merge": zh_merge_profile,
        "organize": organize_profile,
    },
}
