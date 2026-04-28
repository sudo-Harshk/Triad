import asyncio

from client.groq_client import groq_chat_async


def _clean_output(text: str) -> str:
    if "<think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


_ANALYST_SYSTEM = """You are the Analyst.

Use only the provided evidence quote. The background context is for scope only — do not cite facts from it in your verdict.
Do not use outside knowledge or hidden reasoning.

Core rules:
* Be concise.
* Use at least 3 lines in your response.
* Include an exact quote from the provided evidence.
* If the claim goes beyond what the evidence states, label as Unclear.
* If the claim is broader or stronger than the evidence, you MUST NOT mark it as Supported.
* If the claim generalizes beyond the exact wording of the quote, mark it as Partial instead of Supported.
* You MUST distinguish between current state (e.g. "is") and change over time (e.g. "becoming", "increasing", "declining").
* If the claim implies a trend or change not explicitly stated in the quote, you MUST NOT mark it as Supported.
* You MUST NOT infer entities, relationships, or context not explicitly stated in the quote.
* If a name is not mentioned in the quote, treat it as absent.
* Your final label MUST match your reasoning exactly.
* If your reasoning says the evidence is incomplete, you MUST NOT output "Supported".

Preferred output style:
Label: Supported / Not supported / Partial / Unclear
Reason: ...
Evidence: "..."
Limitation: ..."""

_CRITIC_SYSTEM = """You are the Critic.

Use only the provided evidence quote. The background context is for scope only — do not cite facts from it in your verdict.
Do not use outside knowledge or hidden reasoning.

Core rules:
* Be concise.
* Use at least 3 lines in your response.
* Include or reference an exact quote from the evidence.
* Focus on gaps, limitations, or overreach in the claim.
* If the claim exceeds the evidence, mark it as Not supported or Unclear.
* If you agree, you MUST still identify one limitation or missing assumption.
* Do NOT simply restate the claim or evidence.
* You MUST distinguish between current state (e.g. "is") and change over time (e.g. "becoming", "increasing", "declining").
* If the claim changes the tense, scope, or implication of the quote, you MUST mark it as Not supported or Partial.
* You MUST NOT infer entities, relationships, or context not explicitly stated in the quote.
* Your final label MUST match your reasoning exactly.

Preferred output style:
Label: Supported / Not supported / Partial / Unclear
Reason: ..."""

_ALTERNATIVE_SYSTEM = """You are the Alternative.

Use only the provided evidence quote. The background context is for scope only — do not cite facts from it in your verdict.
Do not use outside knowledge or hidden reasoning.

Core rules:
* Be concise.
* Use at least 3 lines in your response.
* Offer a different valid interpretation of the same evidence.
* Do not add new facts beyond the quote.
* If the claim exceeds the evidence, treat it as unsupported or unclear.
* You MUST distinguish between current state and change over time.
* Do NOT reinterpret the quote to imply trends, causes, or changes not explicitly stated.
* You MUST NOT infer entities or context not explicitly stated in the quote.
* You MUST NOT end with a verdict like "Supported". Only provide interpretation.
* Do NOT assign a label.

Preferred output style:
Interpretation: ...
Evidence: "..."
Limitation: ..."""

_CHAIRMAN_SYSTEM = """You are the Chairman.

Use only the provided evidence quote. The background context is for scope only.
Do not use outside knowledge or hidden reasoning.

Core rules:
* Decide only from evidence strength, not role agreement.
* Use at least 3 lines in your response.
* If the claim extends beyond the evidence, choose Unclear.
* If the claim is broader or stronger than the evidence, you MUST NOT output Final: Supported.
* You MUST distinguish between current state and change over time.
* You MUST NOT infer entities or context not explicitly stated in the quote.
* Your final label MUST match your reasoning exactly.
* If your reasoning says the evidence is incomplete, you MUST NOT output Final: Supported.
* Be concise and quote the evidence.

Preferred output style:
Final: Supported / Unsupported / Unclear
Why: ...
Evidence: "..."
Conflict:
Analyst -> ...
Critic -> ..."""


async def run_council(claim: str, chunk_text: str, evidence: str = "") -> dict[str, str]:
    """
    Run the 4-role council on a single claim.

    Analyst, Critic, and Alternative fire in parallel via asyncio.gather.
    Chairman runs after all three complete, receiving their outputs.
    """
    evidence_text = str(evidence or "").strip()
    if isinstance(claim, dict):
        if not evidence_text:
            evidence_text = str(claim.get("evidence", "") or "").strip()
        claim = str(claim.get("claim", "") or "").strip()
    else:
        claim = str(claim or "").strip()

    chunk_snippet = str(chunk_text or "").strip()[:1200]

    base_context = (
        f"Claim:\n{claim}\n\n"
        f"Evidence (primary source — base your verdict on this):\n\"{evidence_text}\"\n\n"
        f"Background context (scope understanding only — do not introduce facts from here into your verdict):\n{chunk_snippet}"
    )

    analyst_prompt = base_context + "\n\nAnalyze whether the evidence supports the claim."
    critic_prompt = base_context + "\n\nAssess whether the claim is supported by the evidence."
    alternative_prompt = base_context + "\n\nProvide an independent assessment of the claim."

    analyst_raw, critic_raw, alternative_raw = await asyncio.gather(
        groq_chat_async(analyst_prompt, system_prompt=_ANALYST_SYSTEM, model="qwen/qwen3-32b", temperature=0.0),
        groq_chat_async(critic_prompt, system_prompt=_CRITIC_SYSTEM, model="llama-3.1-8b-instant", temperature=0.0),
        groq_chat_async(alternative_prompt, system_prompt=_ALTERNATIVE_SYSTEM, model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0.0),
    )

    analyst = _clean_output(analyst_raw)
    critic = _clean_output(critic_raw)
    alternative = _clean_output(alternative_raw)

    chairman_prompt = (
        base_context
        + "\n\nAnalyst:\n" + analyst
        + "\n\nCritic:\n" + critic
        + "\n\nAlternative:\n" + alternative
        + "\n\nNow provide the final judgment."
    )

    judgment = _clean_output(
        await groq_chat_async(
            chairman_prompt,
            system_prompt=_CHAIRMAN_SYSTEM,
            model="llama-3.3-70b-versatile",
            temperature=0.0,
        )
    )

    return {
        "analyst": analyst,
        "critic": critic,
        "alternative": alternative,
        "judgment": judgment,
    }
