import re


_SPACE_RE = re.compile(r"\s+")


def _clean_text(text: str) -> str:
    text = text or ""
    text = _SPACE_RE.sub(" ", text).strip()
    # Fix spacing around punctuation (keep consistent with normalization)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([(\[{])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]}])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"\s+'", "'", text)
    text = re.sub(r"'\s+", "'", text)
    text = re.sub(r'\s+"', '"', text)
    text = re.sub(r'"\s+', '"', text)
    return text.strip()


def _approx_token_limit_to_char_limit(token_limit: int) -> int:
    """
    Approximate: 1 token ~= 4 characters in English-like text.
    Keep deterministic; no model/tokenizer calls.
    """
    return int(token_limit * 4)


def chunk_transcript(transcript: list[dict]) -> list[dict]:
    """
    Convert normalized transcript segments into coherent chunks.

    Input: list of {text, start, end}
    Output: list of {text, start, end}

    Rules:
    - Combine segments sequentially
    - Do NOT break sentences (segment boundaries are treated as sentence-safe)
    - Preserve timestamps:
      start = first segment start, end = last segment end
    - Limit chunk size (~1500–2000 tokens equivalent), approximated via char count
    """
    segments = transcript or []
    if not segments:
        return []

    # Aim for the middle of the requested range; tolerate some variance.
    soft_char_limit = _approx_token_limit_to_char_limit(1800)  # ~7200 chars
    hard_char_limit = _approx_token_limit_to_char_limit(2000)  # ~8000 chars

    chunks: list[dict] = []
    buf_text_parts: list[str] = []
    buf_start: float | None = None
    buf_end: float | None = None
    buf_chars = 0

    def flush():
        nonlocal buf_text_parts, buf_start, buf_end, buf_chars
        if not buf_text_parts:
            buf_start = None
            buf_end = None
            buf_chars = 0
            return

        text = _clean_text(" ".join(buf_text_parts))
        if text:
            chunks.append(
                {
                    "text": text,
                    "start": float(buf_start or 0.0),
                    "end": float(buf_end or (buf_start or 0.0)),
                }
            )
        buf_text_parts = []
        buf_start = None
        buf_end = None
        buf_chars = 0

    for seg in segments:
        t = _clean_text(str(seg.get("text", "") or ""))
        if not t:
            continue

        s = float(seg.get("start", 0.0) or 0.0)
        e = float(seg.get("end", s) or s)
        if e < s:
            e = s

        # If this segment would push us past the soft limit, flush first
        # (but only if we already have content, to avoid empty chunks).
        add_len = len(t) + (1 if buf_text_parts else 0)
        projected = buf_chars + add_len
        if buf_text_parts and projected > soft_char_limit:
            flush()

        if buf_start is None:
            buf_start = s
        buf_end = e
        buf_text_parts.append(t)
        buf_chars += add_len

        # If we exceed the hard limit after adding, flush immediately.
        # This still does not break sentences (segment boundaries only).
        if buf_chars >= hard_char_limit:
            flush()

    flush()
    return chunks

