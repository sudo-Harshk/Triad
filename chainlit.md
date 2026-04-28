# Triad — Evidence-Grounded Claim Verification

Triad analyzes YouTube video transcripts and produces verifiable judgments on key claims through a structured multi-agent council.

## How it works

1. **Paste a YouTube URL** — Triad fetches and cleans the full transcript
2. **Claims are extracted** — 2–5 non-trivial, interpretive claims are identified with exact supporting quotes, spanning the entire video
3. **Council evaluates each claim** using only the quoted evidence:
   - **Analyst** — structured assessment (Label, Reason, Evidence, Limitation)
   - **Critic** — independent challenge; must identify at least one flaw even in agreement
   - **Alternative** — constrained reinterpretation without introducing new facts
   - **Chairman** — final verdict based on evidence strength alone, not role agreement
4. **Verdict is rendered** — Supported / Unsupported / Unclear with a confidence score

## Rules the system enforces

- **No external knowledge** — all reasoning is bounded by the quoted text
- **No entity inference** — if a name isn't in the quote, it doesn't exist in the verdict
- **No semantic drift** — "is" cannot become "becoming"; "suggests" cannot become "proves"
- **Every verdict cites a limitation** — even Supported claims must acknowledge scope boundaries
- **Evidence must directly ground the claim** — vague or tangential quotes are rejected at extraction

## Tips

- Works best with videos that have closed captions (auto-generated or manual)
- Longer, more substantive videos yield richer claims
- After analysis, ask a follow-up question referencing a keyword from any claim
- Re-pasting the same URL replays the cached analysis instantly

## Example

```
https://www.youtube.com/watch?v=...
```

Paste any YouTube URL below to begin.
