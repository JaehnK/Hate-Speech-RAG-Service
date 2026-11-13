"""Download the public comments of YouTube videos as experiment inputs.

Comment text stays under experiments/outputs (git-ignored); only labels keyed by item_id are
versioned. Author names are dropped; the video title is kept for prompt v0.7.1. Usage:

    uv run python -m experiments.fetch_youtube_comments VIDEO_ID [VIDEO_ID ...] \
        --output-path experiments/outputs/youtube/comments.inputs.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.external.youtube import YouTubeApiClient


def item_id(video_id: str, comment_id: str) -> str:
    return f"yt:{video_id}:{comment_id}"


def fetch(client: YouTubeApiClient, video_id: str) -> list[dict]:
    title = client.get_video(video_id)["snippet"]["title"]
    rows = []
    for record in client.iter_comments(video_id):
        text = record.text_original.strip()
        if not text:
            continue
        rows.append(
            {
                "item_id": item_id(video_id, record.youtube_comment_id),
                "source_type": "reply" if record.is_reply else "comment",
                "text": text,
                "video_id": video_id,
                "video_title": title,
                "like_count": record.like_count,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video_ids", nargs="+")
    parser.add_argument("--output-path", type=Path, required=True)
    args = parser.parse_args()

    client = YouTubeApiClient(Settings().youtube_api_key)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_path.open("w", encoding="utf-8") as file:
        for video_id in args.video_ids:
            rows = fetch(client, video_id)
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(json.dumps({"video_id": video_id, "items": len(rows)}))


if __name__ == "__main__":
    main()
