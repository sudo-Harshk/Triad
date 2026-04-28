import os

from groq import AsyncGroq, Groq


def groq_chat(
    prompt: str,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    model: str = "llama-3.1-8b-instant",
) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    client = Groq(api_key=api_key)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    completion = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,
    )

    return (completion.choices[0].message.content or "").strip()


async def groq_chat_async(
    prompt: str,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.0,
    model: str = "llama-3.1-8b-instant",
) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    client = AsyncGroq(api_key=api_key)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    completion = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,
    )

    return (completion.choices[0].message.content or "").strip()
