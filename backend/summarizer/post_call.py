import json
from groq import Groq
from config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

SUMMARY_PROMPT = """You are analyzing a meeting transcript. Return ONLY valid JSON
(no markdown fences, no preamble, no explanation) with this exact structure:

{{
  "summary": "2-3 sentence overview of the meeting",
  "key_points": ["point 1", "point 2"],
  "follow_up_questions": ["question 1", "question 2"]
}}

Transcript:
{transcript}
"""


def summarize_transcript(transcript: str) -> dict:
    """Send a transcript to Groq (Llama 3.3 70B) and get back structured summary data."""
    prompt = SUMMARY_PROMPT.format(transcript=transcript)

    response = client.chat.completions.create(
        model=settings.GROQ_SUMMARY_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.choices[0].message.content.strip()

    # Defensive cleanup in case the model wraps output in ```json fences anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)