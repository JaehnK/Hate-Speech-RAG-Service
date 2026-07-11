import pytest

from app.core.errors import DomainError
from app.jobs.video_id import extract_video_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("abcdefghijk", "abcdefghijk"),
        ("https://www.youtube.com/watch?v=abcdefghijk&t=10", "abcdefghijk"),
        ("https://youtu.be/abcdefghijk", "abcdefghijk"),
        ("youtube.com/shorts/abcdefghijk", "abcdefghijk"),
        ("https://www.youtube.com/embed/abcdefghijk", "abcdefghijk"),
    ],
)
def test_extract_video_id(value, expected) -> None:
    assert extract_video_id(value) == expected


def test_rejects_non_youtube_input() -> None:
    with pytest.raises(DomainError) as exc_info:
        extract_video_id("https://example.com/watch?v=abcdefghijk")
    assert exc_info.value.code == "INVALID_INPUT"
