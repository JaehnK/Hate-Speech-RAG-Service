import re
from urllib.parse import parse_qs, urlparse

from app.core.errors import DomainError


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(input_value: str) -> str:
    value = input_value.strip()
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    candidate = None
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            candidate = parsed.path.split("/")[2]
    elif host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]

    if candidate and VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate
    raise DomainError("INVALID_INPUT", "유효한 YouTube URL 또는 video ID가 아닙니다.", status_code=400)
