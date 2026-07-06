import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Postgres connection string — use the Supabase POOLER string, not the
    # direct db.xxxx.supabase.co host (avoids DNS/IPv6 issues on some networks)
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/video_rag")

    # Local embedding model — 384-dim output, fast, runs on CPU, no API cost
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    EMBEDDING_DIM = 384

    # Chunking settings (character-based, not token-based, for simplicity)
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50

    # Groq API key — used by summarizer/post_call.py (post-call summaries)
    # and live/suggester.py (live in-call suggestions)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    # Groq model names — separate settings so you can tune speed vs. quality
    # independently for each use case (live suggestions need to be fast;
    # post-call summaries can afford a slightly slower/bigger model)
    GROQ_SUMMARY_MODEL = os.getenv("GROQ_SUMMARY_MODEL", "llama-3.3-70b-versatile")
    GROQ_LIVE_MODEL = os.getenv("GROQ_LIVE_MODEL", "llama-3.1-8b-instant")

    # Deepgram key, used for live streaming transcription
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

    # Live suggestion tuning
    LIVE_SUGGESTION_INTERVAL = 8       # min seconds between suggestion generations
    LIVE_SUGGESTION_MIN_CHARS = 80     # don't bother generating on tiny transcript fragments


settings = Settings()

# Fail fast if required keys are missing, rather than crashing deep inside
# a request/pipeline with a confusing AttributeError or None-related error.
_required_keys = {
    "DATABASE_URL": settings.DATABASE_URL,
    "GROQ_API_KEY": settings.GROQ_API_KEY,
    "DEEPGRAM_API_KEY": settings.DEEPGRAM_API_KEY,
}
_missing = [name for name, value in _required_keys.items() if not value]
if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}. "
        f"Check your .env file against .env.example."
    )