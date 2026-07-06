import json
from psycopg2 import pool
from config import settings

_pool = None


def get_pool():
    """Lazily create a small connection pool (reused across requests)."""
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(1, 10, settings.DATABASE_URL)
    return _pool


def get_connection():
    return get_pool().getconn()


def release_connection(conn):
    get_pool().putconn(conn)


def insert_document(external_id: str, source_type: str, text: str, metadata: dict, embedding: list[float]):
    """Store one chunk + its embedding in the documents table."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents (external_id, source_type, text, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s::vector)
            """,
            (external_id, source_type, text, json.dumps(metadata), embedding),
        )
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)


def search_similar(query_embedding: list[float], source_type: str = None, limit: int = 5):
    """
    Find the most similar chunks to a query embedding.
    `<=>` is pgvector's cosine distance operator (smaller = more similar);
    converted to a 0-1 similarity score here for readability. The explicit
    `::vector` cast is required — Postgres won't implicitly cast an array
    parameter to `vector` inside an operator expression.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        if source_type:
            cur.execute(
                """
                SELECT id, external_id, source_type, text, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM documents
                WHERE source_type = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, source_type, query_embedding, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, external_id, source_type, text, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, limit),
            )
        rows = cur.fetchall()
        cur.close()
    finally:
        release_connection(conn)

    return [
        {
            "id": r[0],
            "external_id": r[1],
            "source_type": r[2],
            "text": r[3],
            "metadata": r[4],
            "similarity": float(r[5]),
        }
        for r in rows
    ]