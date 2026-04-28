# Triad

**Evidence-grounded claim verification for YouTube transcripts.**

Triad extracts interpretive claims from a YouTube video and runs each one through a structured 4-role council — Analyst, Critic, Alternative, and Chairman — that evaluates the claim using only the quoted evidence. Every verdict is traceable to the source text, with no external knowledge or entity inference allowed.

---

## How it works

```
YouTube URL
    │
    ▼
Transcript fetch (Supadata)
    │
    ▼
Normalize + chunk (sentence-safe, ~1800 token windows)
    │
    ▼
Claim extraction (batched LLM, interpretive + debatable only)
    │
    ▼
Council per claim ── Analyst ──┐
                 ├── Critic    ├─ parallel
                 └── Alternative ┘
                        │
                    Chairman (sequential, synthesises all three)
                        │
                    Verdict + Confidence score
```

### Council roles

| Role | Model | Job |
|------|-------|-----|
| Analyst | qwen/qwen3-32b | Structured assessment — Label, Reason, Evidence, Limitation |
| Critic | llama-3.1-8b-instant | Independent challenge; must find at least one flaw even in agreement |
| Alternative | llama-4-scout-17b | Constrained reinterpretation without introducing new facts |
| Chairman | llama-3.3-70b-versatile | Final verdict from evidence strength, not role consensus |

### Hard rules the system enforces

- No external knowledge — reasoning is bounded by the quoted evidence
- No entity inference — if a name isn't in the quote, it doesn't exist in the verdict
- No semantic drift — "is" cannot become "becoming"; "suggests" cannot become "proves"
- Every verdict cites a limitation, even when Supported

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Groq API key](https://console.groq.com/keys)
- A [Supadata API key](https://supadata.ai)

### Install

```bash
git clone https://github.com/your-username/triad.git
cd triad

# with uv
uv sync

# or with pip
pip install -e .
```

### Configure

```bash
cp .env.example .env
# fill in your GROQ_API_KEY and SUPADATA_API_KEY
```

### Run

```bash
chainlit run app/main.py
# open http://localhost:8000
```

---

## Usage

1. Paste a YouTube URL into the chat input and press Enter
2. Triad fetches the transcript, extracts claims, and runs the council — progress is shown step by step
3. Each claim block shows:
   - The interpretive claim
   - The exact evidence quote from the transcript
   - Verdict (Supported / Unsupported / Unclear) with a confidence bar
   - Expandable council details (Analyst · Critic · Alternative)
4. Re-paste the same URL to replay the cached analysis instantly
5. After analysis, ask a follow-up question referencing a keyword from any claim

### Supported URL formats

```
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
```

The video must have closed captions (auto-generated or manual).

---

## Project structure

```
app/
├── main.py                  # Chainlit entry point
├── client/
│   ├── groq_client.py       # Shared sync + async Groq client
│   └── supadata_client.py   # YouTube transcript fetcher
└── services/
    ├── transcript.py        # Normalize raw segments into clean sentences
    ├── chunking.py          # Split into ~1800-token chunks
    ├── claim_extractor.py   # Batched LLM claim extraction + validation
    ├── council.py           # 4-role council with parallel async roles
    ├── scoring.py           # Confidence scoring from role labels
    └── validator.py         # Evidence grounding check
```

---

## Tech stack

| Layer | Tool |
|-------|------|
| UI | [Chainlit](https://chainlit.io) |
| LLM inference | [Groq](https://groq.com) |
| Transcript | [Supadata](https://supadata.ai) |
| Package manager | [uv](https://docs.astral.sh/uv/) |
