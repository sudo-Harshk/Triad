<div align="center">

# Triad

**Evidence-grounded claim verification for YouTube transcripts**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-triad--55mk.onrender.com-brightgreen?style=for-the-badge&logo=render)](https://triad-55mk.onrender.com/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Chainlit](https://img.shields.io/badge/UI-Chainlit-ff6b6b?style=for-the-badge)](https://chainlit.io)
[![Groq](https://img.shields.io/badge/LLM-Groq-f55036?style=for-the-badge)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

Paste a YouTube URL. Get traceable, evidence-bounded verdicts on every interpretive claim.

[**Try it live →**](https://triad-55mk.onrender.com/)

</div>

---

## What is Triad?

Triad fetches the transcript of any YouTube video, extracts its **interpretive claims** - the non-obvious, debatable statements the speaker is making - and runs each one through a **structured 4-role council** that evaluates the claim using *only* the quoted evidence.

Every verdict is:
- **Traceable** - linked to an exact quote from the transcript
- **Bounded** - no external knowledge, no entity inference, no semantic drift
- **Scored** - a weighted confidence score from three independent roles

---

## How it works

```
YouTube URL
    │
    ▼
Transcript fetch          ← Supadata API
    │
    ▼
Normalize + chunk         ← sentence-safe, ~1,800-token windows
    │
    ▼
Claim extraction          ← batched LLM, interpretive & debatable claims only
    │
    ▼
Council (per claim)
    ├── Analyst     ──┐
    ├── Critic       ├── parallel (asyncio.gather)
    └── Alternative ─┘
            │
        Chairman          ← sequential, synthesises all three outputs
            │
    Verdict + Confidence score
```

### The Council

| Role | Model | Responsibility |
|------|-------|----------------|
| **Analyst** | `qwen/qwen3-32b` | Structured assessment - Label, Reason, Evidence, Limitation |
| **Critic** | `llama-3.1-8b-instant` | Independent challenge; must find at least one flaw even in agreement |
| **Alternative** | `meta-llama/llama-4-scout-17b` | Constrained reinterpretation without introducing new facts |
| **Chairman** | `llama-3.3-70b-versatile` | Final verdict from evidence strength alone, not role consensus |

### Confidence Scoring

The confidence score (0–100%) is a **weighted blend** across three roles:

| Role | Weight |
|------|--------|
| Chairman | 50% |
| Analyst | 30% |
| Critic | 20% |

Labels map to: `Supported → 100`, `Partial → 50`, `Unclear → 25`, `Unsupported → 0`

### Hard Rules

The system enforces these constraints at every role:

- **No external knowledge** - reasoning is bounded entirely by the quoted evidence
- **No entity inference** - if a name isn't in the quote, it doesn't exist in the verdict
- **No semantic drift** - `"is"` cannot become `"becoming"`; `"suggests"` cannot become `"proves"`
- **Every verdict cites a limitation** - even `Supported` claims acknowledge scope boundaries
- **Evidence must ground the claim** - vague or tangential quotes are rejected at extraction

---

## Live Demo

The app is deployed on Render:

**[https://triad-55mk.onrender.com/](https://triad-55mk.onrender.com/)**

> **Note:** The free tier spins down after inactivity - first load may take ~30 seconds.

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Groq API key](https://console.groq.com/keys)
- A [Supadata API key](https://supadata.ai)

### Install

```bash
git clone https://github.com/sudo-Harshk/triad.git
cd triad

# with uv (recommended)
uv sync

# or with pip
pip install -e .
```

### Configure

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
SUPADATA_API_KEY=your_supadata_api_key_here
```

### Run

```bash
chainlit run app/main.py
# open http://localhost:8000
```

---

## Usage

1. **Paste a YouTube URL** into the chat and press Enter
2. Triad fetches the transcript, extracts claims, and runs the council - progress is shown step by step
3. Each claim block shows:
   - The interpretive claim
   - The exact evidence quote from the transcript
   - Verdict (`Supported` / `Unsupported` / `Unclear`) with a confidence bar
   - Expandable council details - Analyst · Critic · Alternative
4. **Re-paste the same URL** to replay the cached analysis instantly
5. **Ask a follow-up question** referencing a keyword from any claim after analysis

---

## Project Structure

```
app/
├── main.py                  # Chainlit entry point & pipeline orchestration
├── client/
│   ├── groq_client.py       # Sync + async Groq wrappers
│   └── supadata_client.py   # YouTube transcript fetcher
└── services/
    ├── transcript.py        # Normalize raw segments into clean sentences
    ├── chunking.py          # Split into ~1,800-token chunks
    ├── claim_extractor.py   # Batched LLM claim extraction + validation
    ├── council.py           # 4-role council with parallel async evaluation
    ├── scoring.py           # Confidence scoring from role labels
    └── validator.py         # Evidence grounding check
```

---

## Tech Stack

| Layer | Tool |
|-------|------|
| UI & chat runtime | [Chainlit](https://chainlit.io) |
| LLM inference | [Groq](https://groq.com) |
| Transcript source | [Supadata](https://supadata.ai) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Deployment | [Render](https://render.com) |

---

## Design Decisions

**Why a council instead of a single model?**  
A single model asked to evaluate a claim will often confirm it. Three independent roles with different mandates - structured analysis, adversarial critique, and alternative interpretation - surface disagreements that a single pass would miss. The Chairman synthesises evidence strength, not vote count.

**Why Groq?**  
Speed. Three parallel LLM calls per claim need to complete fast to keep the UI responsive. Groq's inference speed makes this practical at the model sizes used.

**Why evidence-bounded rules?**  
Most fact-checking systems fail by importing world knowledge into local verdicts. Triad's hard rules prevent this: if the evidence doesn't say it, the system can't say it either.

---

## Acknowledgements

Triad's council architecture was inspired by [Andrej Karpathy](https://github.com/karpathy)'s [llm-council](https://github.com/karpathy/llm-council) - the idea of running multiple LLM roles against a single problem and synthesising their outputs into a final judgment.

---

## License

This project is licensed under the [MIT License](LICENSE).  
Copyright © 2026 [sudo-Harshk](https://github.com/sudo-Harshk)

---

<div align="center">

Built by [sudo-Harshk](https://github.com/sudo-Harshk) · [Live Demo](https://triad-55mk.onrender.com/) · [MIT License](LICENSE)

</div>
