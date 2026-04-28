_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "and", "in", "it", "that", "this", "for", "on", "with",
    "as", "at", "by", "from", "or", "but", "not", "so", "if", "do",
    "did", "does", "have", "has", "had", "will", "would", "can", "could",
    "its", "their", "they", "we", "you", "he", "she", "i", "my", "our",
}


def is_grounded(claim: str, evidence: str, threshold: float = 0.25) -> bool:
    """
    Returns True if at least `threshold` fraction of content words in the claim
    appear in the evidence. Stop-words are excluded so short function words
    don't inflate the overlap score.
    """
    claim_words = {w.strip(".,;:!?\"'") for w in claim.lower().split() if w not in _STOP_WORDS}
    ev_words = {w.strip(".,;:!?\"'") for w in evidence.lower().split() if w not in _STOP_WORDS}

    if not claim_words:
        return False

    overlap = len(claim_words & ev_words) / len(claim_words)
    return overlap >= threshold
