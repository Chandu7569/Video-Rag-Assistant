from groq import Groq
from config import settings
from rag.retrieve import retrieve

client = Groq(api_key=settings.GROQ_API_KEY)

SUGGESTION_PROMPT = """You are a live meeting assistant. Based on the recent
conversation and the retrieved context below, provide ONE brief, actionable
suggestion or answer (2-3 sentences max) that would help the person on the
call right now. If nothing useful applies, respond with exactly: No suggestion.

Recent conversation:
{transcript}

Retrieved context:
{context}
"""


def generate_suggestion(recent_transcript: str) -> str:
    """Retrieve relevant context and ask Groq for a short, live suggestion."""
    results = retrieve(recent_transcript, limit=3)
    context = "\n---\n".join(r["text"] for r in results) if results else "No relevant context found."

    prompt = SUGGESTION_PROMPT.format(transcript=recent_transcript, context=context)

    response = client.chat.completions.create(
        model=settings.GROQ_LIVE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content.strip()