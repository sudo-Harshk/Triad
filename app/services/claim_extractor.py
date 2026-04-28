import json

from client.groq_client import groq_chat


BATCH_SIZE = 3
MAX_CLAIMS = 5

SYSTEM_PROMPT = """You are extracting key claims from a transcript.

You MUST respond in English only. Claims MUST be written in English only.

Return ONLY valid JSON.

STRICT OUTPUT RULES:

* Output must be a valid JSON array
* No markdown, no explanation
* No text before or after JSON

Each item:
{
"claim": "...",
"timestamp": number,
"evidence": "exact quote"
}

---

STRICT EXTRACTION RULES:

1. Claims must be INTERPRETIVE (not literal):

* Extract INTERPRETIVE claims, not literal statements
* Claims should express meaning or implication, not just restate features

Bad: "AI can summarize emails"
Good: "The system presents AI capabilities as broad lifestyle automation tools"

2. Claims must be DEBATABLE:

* Prefer claims that could be challenged, questioned, or interpreted differently
* Avoid obvious best practices or universally accepted advice
* Avoid generic statements like "you should do X"

3. Evidence MUST directly support the claim:

* The claim must be clearly grounded in the quoted text
* If the quote does not strongly support the claim → DO NOT include it
* Reject claims that introduce concepts not explicitly present in the transcript.
* Claims must be directly traceable to the provided text.
* Do NOT return claims that are identical or nearly identical to a single sentence in the transcript.
* Claims must involve some level of interpretation, implication, or generalization beyond the exact wording.
* Reject claims that are purely subjective statements without an implied argument, comparison, or causal meaning.

4. Timestamp MUST be grounded:

* You MUST take timestamp from the [start–end] markers provided
* Use the START time of the chunk as timestamp
* DO NOT invent timestamps
* DO NOT extrapolate

5. Use ONLY the provided transcript

6. Max 5 claims

7. If no good claims exist → return []

---

Bad example (REJECT):
Claim: "AI agents should not have production DB access"
Reason: obvious, not debatable

Good example (ACCEPT):
Claim: "AI-generated SQL is unreliable because it often misses required tables or logic"
Reason: can be challenged

---

Return ONLY JSON."""


_TRIVIAL_STARTS = (
    "you should", "it is important", "always ", "never ", "make sure",
    "remember to", "one way to", "a good way", "best practice",
    "it's important", "it's a good", "you need to", "you must",
)

_DEBATABLE_SIGNALS = {
    "suggests", "implies", "because", "despite", "although", "however",
    "but", "argues", "claims", "reveals", "positions", "frames", "treats",
    "presents", "constructs", "assumes", "conflates", "overstates",
    "understates", "prioritizes", "signals", "reflects", "indicates",
    "represents", "may", "could", "might", "arguably", "potentially",
    "rather", "instead", "whereas", "unlike", "contrasts", "misleads",
    "exaggerates", "downplays", "reframes", "obscures",
}


def _normalize_for_match(s: str) -> str:
    return " ".join((s or "").replace("–", "-").replace("—", "-").split()).strip().lower()


def _is_debatable(claim: str) -> bool:
    c = (claim or "").lower().strip()
    if len(c.split()) < 8:
        return False
    if any(c.startswith(t) for t in _TRIVIAL_STARTS):
        return False
    return True


def _simple_match(evidence: str, text: str) -> bool:
    return _normalize_for_match(evidence) in _normalize_for_match(text)


def is_trivial(claim: str, evidence: str) -> bool:
    c = (claim or "").lower().strip()
    e = (evidence or "").lower().strip()
    if c == e:
        return True
    c_words = set(c.split())
    e_words = set(e.split())
    overlap = len(c_words & e_words) / max(len(c_words), 1)
    return overlap > 0.85


def _is_duplicate(item: dict, seen: list[dict]) -> bool:
    c_words = set(item["claim"].lower().split())
    for s in seen:
        s_words = set(s["claim"].lower().split())
        overlap = len(c_words & s_words) / max(len(c_words), 1)
        if overlap > 0.80:
            return True
    return False


def _extract_claims_from_batch(batch: list[dict]) -> list[dict]:
    """Run one LLM call against a batch of chunks, return validated claim dicts."""
    transcript_lines: list[str] = ["Transcript:"]
    chunk_ranges: list[tuple[float, float]] = []
    chunk_texts: list[str] = []

    for ch in batch:
        text = str(ch.get("text", "") or "").strip()
        if not text:
            continue
        start = float(ch.get("start", 0.0) or 0.0)
        end = float(ch.get("end", start) or start)
        chunk_ranges.append((start, end))
        chunk_texts.append(text)
        transcript_lines.append(f"[{start:.1f}–{end:.1f}] {text}")
        transcript_lines.append("")

    if not chunk_texts:
        return []

    user_prompt = (
        "\n".join(transcript_lines).strip()
        + "\n\nExtract INTERPRETIVE claims (not literal statements). Claims must be written in English only."
    )

    content = groq_chat(user_prompt, system_prompt=SYSTEM_PROMPT, temperature=0.2)
    print("RAW LLM OUTPUT:", content[:500])
    content = content.strip()

    # Strip markdown code fences if present
    if "```" in content:
        for part in content.split("```"):
            part = part.strip()
            if part.startswith(("{", "[")):
                content = part
                break

    try:
        data = json.loads(content)
    except Exception:
        return []

    if not isinstance(data, list):
        if isinstance(data, dict):
            if "claims" in data:
                data = data["claims"]
            elif "data" in data:
                data = data["data"]
            else:
                return []
        else:
            return []

    valid: list[dict] = []
    for c in data:
        if not isinstance(c, dict):
            continue
        claim = str(c.get("claim", "")).strip()
        evidence = str(c.get("evidence", "")).strip()
        if not claim or not evidence:
            print(f"  DROP (empty): {c}")
            continue
        if not _is_debatable(claim):
            print(f"  DROP (not debatable): {claim!r}")
            continue
        if is_trivial(claim, evidence):
            print(f"  DROP (trivial): {claim!r}")
            continue

        # Ground the claim to a real chunk in this batch
        source_chunk = None
        for i, txt in enumerate(chunk_texts):
            if _simple_match(evidence, txt):
                source_chunk = i
                break
        if source_chunk is None:
            print(f"  DROP (evidence not in chunk): {evidence[:80]!r}")
            continue

        ts_val = float(chunk_ranges[source_chunk][0])
        valid.append({
            "claim": claim,
            "timestamp": ts_val,
            "evidence": evidence,
            "chunk_index": source_chunk,
            "_chunk_text": chunk_texts[source_chunk],
        })

    return valid


def extract_claims(chunks: list[dict]) -> list[dict]:
    """
    Process all chunks in batches of BATCH_SIZE, deduplicate across batches,
    and return up to MAX_CLAIMS validated claims.
    """
    all_valid: list[dict] = []

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_start: batch_start + BATCH_SIZE]
        batch_claims = _extract_claims_from_batch(batch)
        all_valid.extend(batch_claims)
        if len(all_valid) >= MAX_CLAIMS * 3:
            # Have enough candidates; stop early to avoid unnecessary API calls
            break

    # Deduplicate by claim text similarity, keep first occurrence
    seen: list[dict] = []
    for item in all_valid:
        if not _is_duplicate(item, seen):
            seen.append(item)
        if len(seen) >= MAX_CLAIMS:
            break

    print("FINAL CLAIMS:", seen)
    return seen
