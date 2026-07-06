from sentence_transformers import SentenceTransformer
from config import settings

_model = None


def get_model():
    """Lazy-load the model once and reuse it (loading is slow, ~1-2s)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single string into a vector."""
    model = get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple strings at once — much faster than looping embed_text."""
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()