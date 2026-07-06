from rag.chunker import chunk_text
from rag.embed import embed_text
from rag.vector_store import insert_document


def store_transcript(meeting_id: str, transcript: str, metadata: dict) -> int:
    """Store the raw transcript, chunked, under source_type='transcript'."""
    chunks = chunk_text(transcript)
    for chunk in chunks:
        embedding = embed_text(chunk)
        insert_document(meeting_id, "transcript", chunk, metadata, embedding)
    return len(chunks)


def store_summary(meeting_id: str, summary_data: dict, metadata: dict) -> None:
    """Store the generated summary + key points as one searchable entry."""
    summary_text = summary_data["summary"] + " " + " ".join(summary_data["key_points"])
    embedding = embed_text(summary_text)
    combined_metadata = {**metadata, "questions": summary_data["follow_up_questions"]}
    insert_document(meeting_id, "summary", summary_text, combined_metadata, embedding)