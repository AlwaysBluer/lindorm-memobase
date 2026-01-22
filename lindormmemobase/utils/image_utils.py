import base64
import mimetypes
from typing import Optional, Union


# Image magic bytes for format detection (replacement for deprecated imghdr)
_IMAGE_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'\xff\xd8\xff': 'image/jpeg',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # WEBP needs additional check
    b'BM': 'image/bmp',
    b'\x00\x00\x01\x00': 'image/x-icon',
    b'\x00\x00\x02\x00': 'image/x-icon',
}


def ensure_bytes(image_data: Union[bytes, bytearray, memoryview]) -> bytes:
    """Convert image data to bytes."""
    if isinstance(image_data, bytes):
        return image_data
    if isinstance(image_data, (bytearray, memoryview)):
        return bytes(image_data)
    raise ValueError("image_data must be bytes, bytearray, or memoryview")


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


def infer_content_type_from_bytes(image_data: bytes) -> Optional[str]:
    """
    Infer image content type from file magic bytes.
    
    Replaces deprecated imghdr module (removed in Python 3.13).
    """
    if not image_data or len(image_data) < 12:
        return None
    
    # Check PNG
    if image_data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    
    # Check JPEG (starts with FFD8FF)
    if image_data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    
    # Check GIF
    if image_data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    
    # Check WEBP (RIFF....WEBP)
    if image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
        return 'image/webp'
    
    # Check BMP
    if image_data[:2] == b'BM':
        return 'image/bmp'
    
    # Check ICO/CUR
    if image_data[:4] in (b'\x00\x00\x01\x00', b'\x00\x00\x02\x00'):
        return 'image/x-icon'
    
    # Check TIFF (little endian or big endian)
    if image_data[:4] in (b'II*\x00', b'MM\x00*'):
        return 'image/tiff'
    
    return None


def build_data_url(image_data: bytes, content_type: Optional[str] = None) -> str:
    """Build a data URL from image bytes."""
    if content_type is None:
        content_type = infer_content_type_from_bytes(image_data) or "application/octet-stream"
    b64 = base64.b64encode(image_data).decode("ascii")
    return f"data:{content_type};base64,{b64}"
