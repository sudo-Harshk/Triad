_LABEL_SCORE: dict[str, float] = {
    "not supported": 0.0,
    "unsupported": 0.0,
    "unclear": 0.25,
    "partial": 0.5,
    "supported": 1.0,
}


def _extract_score(text: str) -> float:
    """
    Scans role output for the first line containing 'label:' or 'final:' and
    maps it to a numeric score. Returns 0.25 (unclear) when unparseable.
    """
    for line in (text or "").lower().splitlines():
        line = line.strip()
        if not ("label:" in line or "final:" in line):
            continue
        # longest keys first so "not supported" matches before "supported"
        for key in sorted(_LABEL_SCORE, key=len, reverse=True):
            if key in line:
                return _LABEL_SCORE[key]
    return 0.25


def compute_confidence(analyst: str, critic: str, judgment: str) -> int:
    """
    Returns a 0–100 confidence score.

    Weights: Chairman 50%, Analyst 30%, Critic 20%.
    Chairman carries the most authority because it synthesises all role outputs.
    """
    chairman_score = _extract_score(judgment)
    analyst_score = _extract_score(analyst)
    critic_score = _extract_score(critic)

    raw = chairman_score * 0.50 + analyst_score * 0.30 + critic_score * 0.20
    return round(raw * 100)
