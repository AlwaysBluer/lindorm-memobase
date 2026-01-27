import mimetypes
from typing import Optional


def infer_content_type_from_url(url: str) -> Optional[str]:
    """Infer content type from URL extension."""
    if not url:
        return None
    # Handle data URLs
    if url.startswith('data:'):
        try:
            mime_part = url.split(';')[0]
            return mime_part.replace('data:', '')
        except (IndexError, ValueError):
            return None
    content_type, _ = mimetypes.guess_type(url)
    return content_type
