import asyncio
import re

import chainlit as cl
from dotenv import load_dotenv

from client.supadata_client import fetch_transcript
from services.transcript import normalize_transcript
from services.chunking import chunk_transcript
from services.claim_extractor import extract_claims
from services.council import run_council
from services.scoring import compute_confidence


load_dotenv()

_YT_PATTERN = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube\.com/watch\?.*v=[\w-]+|youtu\.be/[\w-]+)"
)

_LABEL_ICON = {
    "Supported": "✅",
    "Unsupported": "❌",
    "Unclear": "⚠️",
}


def _validate_youtube_url(url: str) -> str | None:
    if not url:
        return "Please paste a YouTube URL."
    if not _YT_PATTERN.match(url):
        return (
            "That doesn't look like a YouTube URL.\n\n"
            "Expected formats:\n"
            "- `https://www.youtube.com/watch?v=...`\n"
            "- `https://youtu.be/...`"
        )
    return None


def _parse_judgment(judgment: str) -> tuple[str, str]:
    final_label = "Unclear"
    why = ""
    for line in (judgment or "").splitlines():
        l = line.strip()
        if not l:
            continue
        if l.lower().startswith("final:"):
            val = l.split(":", 1)[1].strip().lower()
            if val.startswith("supported"):
                final_label = "Supported"
            elif val.startswith("unsupported"):
                final_label = "Unsupported"
            else:
                final_label = "Unclear"
        elif l.lower().startswith("why:"):
            why = l.split(":", 1)[1].strip()
    return final_label, why


def _confidence_bar(score: int) -> str:
    filled = round(score / 10)
    return "█" * filled + "░" * (10 - filled) + f"  {score}%"


async def render_claim_block(
    index: int,
    claim: str,
    evidence: str,
    final_label: str,
    why: str,
    confidence: int,
    council: dict,
):
    analyst_output = council.get("analyst", "") or ""
    critic_output = council.get("critic", "") or ""
    alternative_output = council.get("alternative", "") or ""
    icon = _LABEL_ICON.get(final_label, "•")

    block = f"""---

**Claim {index}**
{claim}

**Evidence**
> {evidence}

**Verdict:** {icon} {final_label}
**Confidence:** {_confidence_bar(confidence)}
**Why:** {why}

<details>
<summary>Council details</summary>

**Analyst**

{analyst_output}

**Critic**

{critic_output}

**Alternative**

{alternative_output}

</details>
"""
    await cl.Message(content=block).send()


async def handle_followup(question: str, results: list[dict]):
    q_words = set(question.lower().split())
    best_match = None
    best_score = 0
    for r in results:
        claim_words = set(r["claim"].lower().split())
        score = len(q_words & claim_words)
        if score > best_score:
            best_score = score
            best_match = r

    if not best_match or best_score < 2:
        await cl.Message(
            content=(
                "I couldn't match your question to a specific claim from the last analysis.\n\n"
                "Try referencing a keyword from one of the claims, or paste a new YouTube URL to analyze."
            )
        ).send()
        return

    r = best_match
    await cl.Message(
        content=f"Here's the full council analysis for the most relevant claim:\n\n**{r['claim']}**"
    ).send()
    await render_claim_block(
        index=r["index"],
        claim=r["claim"],
        evidence=r["evidence"],
        final_label=r["final_label"],
        why=r["why"],
        confidence=r["confidence"],
        council=r["council"],
    )


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("last_url", None)
    cl.user_session.set("last_results", [])


@cl.on_message
async def on_message(message: cl.Message):
    user_input = (message.content or "").strip()

    # Not a URL → handle as follow-up question
    if not user_input.startswith("http"):
        results = cl.user_session.get("last_results") or []
        if not results:
            await cl.Message(
                content="Paste a YouTube URL to begin analysis."
            ).send()
            return
        await handle_followup(user_input, results)
        return

    youtube_url = user_input

    # Validate URL format
    err = _validate_youtube_url(youtube_url)
    if err:
        await cl.Message(content=err).send()
        return

    # Same URL → replay cached results
    if youtube_url == cl.user_session.get("last_url"):
        cached = cl.user_session.get("last_results") or []
        if cached:
            await cl.Message(content="Replaying previous analysis for this URL.").send()
            for r in cached:
                await render_claim_block(
                    index=r["index"],
                    claim=r["claim"],
                    evidence=r["evidence"],
                    final_label=r["final_label"],
                    why=r["why"],
                    confidence=r["confidence"],
                    council=r["council"],
                )
            return

    # --- Full pipeline ---

    # Step 1: Fetch transcript
    async with cl.Step(name="Fetching transcript", type="tool") as step:
        try:
            transcript = await asyncio.to_thread(fetch_transcript, youtube_url)
        except RuntimeError as e:
            msg = str(e)
            if "not available" in msg.lower() or "no transcript" in msg.lower():
                friendly = "This video has no captions available. Try a video with closed captions enabled."
            elif "private" in msg.lower() or "403" in msg:
                friendly = "This video is private or restricted."
            elif "not found" in msg.lower() or "404" in msg:
                friendly = "Video not found. Check the URL and try again."
            else:
                friendly = f"Could not fetch transcript: {msg}"
            step.output = f"Failed: {msg}"
            await cl.Message(content=friendly).send()
            return
        step.output = f"{len(transcript)} raw segments"

    # Step 2: Normalize and chunk
    async with cl.Step(name="Normalizing & chunking", type="tool") as step:
        cleaned = normalize_transcript(transcript)
        chunks = chunk_transcript(cleaned)
        step.output = f"{len(chunks)} chunks from {len(cleaned)} segments"

    if not chunks:
        await cl.Message(content="Transcript was empty after cleaning. Try a different video.").send()
        return

    # Step 3: Extract claims
    async with cl.Step(name="Extracting claims", type="tool") as step:
        claims = await asyncio.to_thread(extract_claims, chunks)
        step.output = f"{len(claims)} claims found across {len(chunks)} chunks"

    if not claims:
        await cl.Message(
            content="No strong interpretive claims could be extracted from this transcript. Try a video with more substantive content."
        ).send()
        return

    await cl.Message(content=f"Found **{len(claims)} claim(s)**. Running council evaluation...").send()

    # Step 4: Council per claim
    collected_results: list[dict] = []
    for i, c in enumerate(claims, start=1):
        claim_text = c.get("claim", "")
        evidence = c.get("evidence", "")
        chunk_text = c.get("_chunk_text", "")

        # Fall back to the source chunk if _chunk_text wasn't stored
        if not chunk_text:
            chunk_index = int(c.get("chunk_index", -1))
            if 0 <= chunk_index < len(chunks):
                chunk_text = str(chunks[chunk_index].get("text", "") or "").strip()

        async with cl.Step(name=f"Claim {i} — Council", type="llm") as step:
            try:
                council = await run_council(claim_text, chunk_text, evidence)
            except Exception as e:
                step.output = f"Error: {e}"
                print(f"Council error on claim {i}: {e}")
                continue

            judgment = council.get("judgment", "")
            final_label, why = _parse_judgment(judgment)
            confidence = compute_confidence(council["analyst"], council["critic"], judgment)
            step.output = f"{_LABEL_ICON.get(final_label, '•')} {final_label} ({confidence}% confidence)"

        result = {
            "index": i,
            "claim": claim_text,
            "evidence": evidence,
            "final_label": final_label,
            "why": why,
            "confidence": confidence,
            "council": council,
        }
        collected_results.append(result)
        await render_claim_block(**result)

    if not collected_results:
        await cl.Message(content="No valid analysis generated.").send()
        return

    # Persist for replay and follow-up questions
    cl.user_session.set("last_url", youtube_url)
    cl.user_session.set("last_results", collected_results)
