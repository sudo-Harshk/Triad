import re


_NOISE_TAG_RE = re.compile(r"^\s*\[(?:[^\]]+)\]\s*$")
_ANY_BRACKET_TAG_RE = re.compile(r"\[(?:music|applause|laughter|cheers|inaudible|silence|sighs?)\]", re.I)


def _clean_text(text: str) -> str:
    text = text or ""
    text = _ANY_BRACKET_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Fix spacing around punctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([(\[{])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]}])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"\s+'", "'", text)
    text = re.sub(r"'\s+", "'", text)
    text = re.sub(r'\s+"', '"', text)
    text = re.sub(r'"\s+', '"', text)
    return text.strip()


def _is_noise_only(text: str) -> bool:
    if not text:
        return True
    if _NOISE_TAG_RE.match(text):
        return True
    cleaned = _clean_text(text)
    return cleaned == "" or _NOISE_TAG_RE.match(cleaned) is not None


def _ends_sentence(text: str) -> bool:
    t = text.rstrip()
    if not t:
        return False
    # Treat these as sentence-final. Include closing quotes/brackets.
    return bool(re.search(r"[.!?](?:[\"'\)\]\}]*)$", t))


def normalize_transcript(transcript: list[dict]) -> list[dict]:
    """
    Normalize a timestamped transcript into clean segments.

    Input: list of {text, start, end}
    Output: list of {text, start, end}
    """
    cleaned_segments: list[dict] = []

    # 1) Clean + drop noise/empties
    for seg in transcript or []:
        text = str(seg.get("text", "") or "")
        if _is_noise_only(text):
            continue

        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", start) or start)
        text = _clean_text(text)
        if not text:
            continue

        cleaned_segments.append({"text": text, "start": start, "end": end})

    if not cleaned_segments:
        return []

    # 2) Merge fragments into sentence-like units (preserving timestamps)
    merged: list[dict] = []
    buf_text: str = ""
    buf_start: float | None = None
    buf_end: float | None = None

    def flush():
        nonlocal buf_text, buf_start, buf_end
        t = _clean_text(buf_text)
        if t:
            merged.append({"text": t, "start": float(buf_start or 0.0), "end": float(buf_end or (buf_start or 0.0))})
        buf_text = ""
        buf_start = None
        buf_end = None

    for seg in cleaned_segments:
        t = seg["text"]
        s = float(seg["start"])
        e = float(seg["end"])

        if buf_start is None:
            buf_start = s
            buf_end = e
            buf_text = t
            continue

        prev = buf_text.rstrip()
        joiner = " "
        if prev.endswith(("-", "—")):
            joiner = ""
        elif prev.endswith(("(", "[", "{", "“", '"')):
            joiner = ""

        candidate = _clean_text(prev + joiner + t)

        # Heuristics: keep merging until we hit a sentence end, and also absorb tiny fragments.
        is_tiny = len(t) < 18
        should_merge = (not _ends_sentence(prev)) or is_tiny or prev.endswith((",", ":", ";"))

        if should_merge:
            buf_text = candidate
            buf_end = max(buf_end or e, e)
        else:
            flush()
            buf_start = s
            buf_end = e
            buf_text = t

    flush()

    # 3) Final pass: remove accidental double spaces, ensure non-decreasing timestamps
    out: list[dict] = []
    last_end = 0.0
    for seg in merged:
        start = float(seg["start"])
        end = float(seg["end"])
        if end < start:
            end = start
        if start < last_end:
            start = last_end
            if end < start:
                end = start
        last_end = end
        out.append({"text": _clean_text(seg["text"]), "start": start, "end": end})

    return out

