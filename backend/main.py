import os
import shutil
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag.chunker import chunk_text
from rag.embed import embed_text
from rag.vector_store import insert_document
from rag.retrieve import retrieve
from live.session import LiveSession
from live.url_stream import UrlAudioStreamer
from transcription.extract_audio import extract_audio
from transcription.batch_transcribe import transcribe_audio_file
from transcription.download_video import download_audio_from_url
from summarizer.post_call import summarize_transcript
from summarizer.store import store_transcript, store_summary

app = FastAPI(title="Video RAG Assistant - Backend")

# Allows the web UI (hosted on a different domain, e.g. Render static site)
# to call this backend. Restrict allow_origins to your actual web UI's URL
# once you have it, instead of "*", for better security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
UPLOAD_DIR = "uploads_tmp"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class IngestRequest(BaseModel):
    external_id: str
    source_type: str   # 'transcript' | 'summary' | 'doc' | 'crm'
    text: str
    metadata: dict = {}


class RetrieveRequest(BaseModel):
    query: str
    source_type: str | None = None
    limit: int = 5


class UploadUrlRequest(BaseModel):
    url: str
    meeting_id: str


@app.post("/ingest")
def ingest(req: IngestRequest):
    """Chunk, embed, and store a piece of text (doc, transcript, CRM note, etc.)."""
    chunks = chunk_text(req.text)
    for chunk in chunks:
        embedding = embed_text(chunk)
        insert_document(req.external_id, req.source_type, chunk, req.metadata, embedding)
    return {"status": "ok", "chunks_indexed": len(chunks)}


@app.post("/retrieve")
def retrieve_endpoint(req: RetrieveRequest):
    """Query the knowledge base for the most relevant chunks."""
    results = retrieve(req.query, source_type=req.source_type, limit=req.limit)
    return {"results": results}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws/live/{meeting_id}")
async def live_session_ws(websocket: WebSocket, meeting_id: str):
    """
    Desktop app connects here for the duration of a call.
    It streams raw audio bytes in; the server streams suggestion
    messages back as JSON whenever one is generated.
    """
    await websocket.accept()

    async def send_suggestion(text: str, start_time: float, end_time: float):
        await websocket.send_json({
            "type": "suggestion",
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
        })

    async def send_transcript_segment(text: str, start_time: float, end_time: float):
        await websocket.send_json({
            "type": "transcript",
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
        })

    session = LiveSession(meeting_id, on_suggestion=send_suggestion, on_transcript_segment=send_transcript_segment)
    await session.start()

    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            await session.send_audio(audio_chunk)
    except WebSocketDisconnect:
        await session.close()


@app.post("/upload")
async def upload_meeting(file: UploadFile = File(...), meeting_id: str = Form(...)):
    """
    Accepts an uploaded video or audio file, transcribes it (batch, not
    live), summarizes it via Groq, and stores both the transcript and
    summary in the RAG store — same downstream pipeline as
    summarizer/run.py, just triggered from a file instead of a .txt file.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    saved_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    audio_path = None

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Video files need audio extracted first; audio files can go straight through
        audio_path = extract_audio(saved_path) if ext in VIDEO_EXTENSIONS else saved_path

        transcript = transcribe_audio_file(audio_path)
        if not transcript.strip():
            return {"status": "error", "message": "No speech detected in the file"}

        summary_data = summarize_transcript(transcript)

        chunk_count = store_transcript(
            meeting_id, transcript, {"source": "upload", "filename": file.filename}
        )
        store_summary(
            meeting_id, summary_data, {"source": "upload", "filename": file.filename}
        )

        return {
            "status": "ok",
            "meeting_id": meeting_id,
            "transcript_chunks_indexed": chunk_count,
            "transcript": transcript,
            "summary": summary_data,
        }
    finally:
        # Clean up temp files regardless of success/failure
        if os.path.exists(saved_path):
            os.remove(saved_path)
        if audio_path and audio_path != saved_path and os.path.exists(audio_path):
            os.remove(audio_path)


@app.post("/upload-url")
async def upload_meeting_from_url(req: UploadUrlRequest):
    """
    Same pipeline as /upload, but starting from a video/recording URL
    (YouTube link, direct file link, or many meeting-recording hosts)
    instead of an uploaded file.
    """
    audio_path = None
    try:
        audio_path = download_audio_from_url(req.url)

        transcript = transcribe_audio_file(audio_path)
        if not transcript.strip():
            return {"status": "error", "message": "No speech detected from that URL"}

        summary_data = summarize_transcript(transcript)

        chunk_count = store_transcript(
            req.meeting_id, transcript, {"source": "url", "url": req.url}
        )
        store_summary(
            req.meeting_id, summary_data, {"source": "url", "url": req.url}
        )

        return {
            "status": "ok",
            "meeting_id": req.meeting_id,
            "transcript_chunks_indexed": chunk_count,
            "transcript": transcript,
            "summary": summary_data,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


@app.websocket("/ws/live-url/{meeting_id}")
async def live_url_session_ws(websocket: WebSocket, meeting_id: str):
    """
    Live-summarizes an ONGOING stream at a URL (e.g. a YouTube Live link),
    as opposed to /upload-url which processes a finished recording.
    Client connects, then sends one JSON message: {"url": "..."}.
    Suggestions stream back the same way as the mic-based live session.
    """
    await websocket.accept()

    init_message = await websocket.receive_json()
    stream_url = init_message.get("url")
    if not stream_url:
        await websocket.send_json({"type": "error", "text": "No URL provided"})
        await websocket.close()
        return

    async def send_suggestion(text: str, start_time: float, end_time: float):
        await websocket.send_json({
            "type": "suggestion",
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
        })

    async def send_transcript_segment(text: str, start_time: float, end_time: float):
        await websocket.send_json({
            "type": "transcript",
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
        })

    # Raw PCM from ffmpeg needs the encoding declared explicitly to Deepgram
    session = LiveSession(
        meeting_id,
        on_suggestion=send_suggestion,
        on_transcript_segment=send_transcript_segment,
        encoding="linear16",
        sample_rate=16000,
    )
    await session.start()

    streamer = UrlAudioStreamer(stream_url, on_audio_chunk=session.send_audio)
    await streamer.start()

    try:
        while True:
            await websocket.receive_text()  # blocks until disconnect; client sends nothing further
    except WebSocketDisconnect:
        pass
    finally:
        await streamer.stop()
        await session.close()