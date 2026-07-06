from rag.embed import embed_text
from rag.vector_store import search_similar


def retrieve(query: str, source_type: str = None, limit: int = 5, summary_first: bool = True):
    """
    Retrieves relevant chunks for a query.

    If summary_first=True and no explicit source_type is given, checks the
    'summary' layer first (fast, high-signal). Falls back to searching
    everything if summaries aren't a strong enough match.
    """
    query_embedding = embed_text(query)

    if source_type:
        return search_similar(query_embedding, source_type=source_type, limit=limit)

    if summary_first:
        summary_results = search_similar(query_embedding, source_type="summary", limit=limit)
        if summary_results and summary_results[0]["similarity"] > 0.5:
            return summary_results

    return search_similar(query_embedding, limit=limit)