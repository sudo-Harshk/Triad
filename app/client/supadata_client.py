import os

from supadata.client import Supadata
from supadata.types import BatchJob, Transcript


def fetch_transcript(youtube_url: str) -> list[dict]:
    api_key = os.getenv("SUPADATA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SUPADATA_API_KEY")

    client = Supadata(api_key=api_key)
    # Important: keep `text=False` so we receive timestamped chunks, not plain text.
    result = client.transcript(youtube_url, text=False)

    if isinstance(result, BatchJob):
        raise RuntimeError("Transcript not available immediately")

    if not isinstance(result, Transcript):
        raise RuntimeError("Unexpected transcript response")

    segments: list[dict] = []
    for chunk in result.content:
        start = float(chunk.offset or 0.0)
        duration = float(chunk.duration or 0.0)
        end = start + duration
        segments.append(
            {
                "text": (chunk.text or "").strip(),
                "start": start,
                "end": end,
            }
        )

    return segments

