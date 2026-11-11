import os
import sys
import shutil
import uuid
import streamlit as st

# ==============================================================================
# 1. Environment & Path Initialization
# ==============================================================================
# Load local .env from backend/.env or root if present
try:
    from dotenv import load_dotenv
    backend_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", ".env")
    if os.path.exists(backend_env):
        load_dotenv(backend_env)
    load_dotenv()
except Exception:
    pass

# Bridge Streamlit Cloud secrets to os.environ so backend/config.py can read them
try:
    if hasattr(st, "secrets"):
        for key, value in st.secrets.items():
            if isinstance(value, str) and key not in os.environ:
                os.environ[key] = value
except Exception:
    pass

# Ensure backend directory is in Python path for direct imports
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from config import settings
    from rag.chunker import chunk_text
    from rag.embed import embed_text
    from rag.vector_store import insert_document, get_connection, release_connection
    from rag.retrieve import retrieve
    from transcription.extract_audio import extract_audio
    from transcription.batch_transcribe import transcribe_audio_file
    from transcription.download_video import download_audio_from_url
    from summarizer.post_call import summarize_transcript
    from summarizer.store import store_transcript, store_summary
    from groq import Groq
    config_error = None
except Exception as e:
    config_error = str(e)

# ==============================================================================
# 2. Database Helper Functions
# ==============================================================================
def get_indexed_meetings():
    """Retrieve unique meetings indexed in the database."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT external_id, COUNT(*) as chunks, MIN(created_at) as created_at
                FROM documents
                GROUP BY external_id
                ORDER BY created_at DESC;
            """)
            rows = cur.fetchall()
            cur.close()
            return [{"id": r[0], "chunks": r[1], "created_at": r[2]} for r in rows]
        finally:
            release_connection(conn)
    except Exception:
        return []

def get_meeting_data(meeting_id: str):
    """Retrieve chunks and summary for a specific meeting."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT source_type, text, metadata, created_at
                FROM documents
                WHERE external_id = %s
                ORDER BY id ASC;
            """, (meeting_id,))
            rows = cur.fetchall()
            cur.close()
            return rows
        finally:
            release_connection(conn)
    except Exception:
        return []

# ==============================================================================
# 3. Streamlit Page Setup & Styling
# ==============================================================================
st.set_page_config(
    page_title="Video RAG Assistant",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom header styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #f2a93b, #8b7cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #9ba0ad;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .card {
        background: rgba(28, 31, 40, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🎙️ Video RAG Assistant & Meeting Co-Pilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Transcribe, summarize, and intelligently query your meetings with PostgreSQL (pgvector) and Groq LLMs.</div>', unsafe_allow_html=True)

# ==============================================================================
# 4. Sidebar Diagnostics & Indexed Meetings
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Configuration & Status")
    
    # Environment status checks
    has_db = bool(os.getenv("DATABASE_URL"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_deepgram = bool(os.getenv("DEEPGRAM_API_KEY"))

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Postgres / pgvector")
        st.write("🟢 Connected" if has_db else "🔴 Missing")
        st.caption("Deepgram ASR")
        st.write("🟢 Configured" if has_deepgram else "🔴 Missing")
    with col_b:
        st.caption("Groq LLM")
        st.write("🟢 Configured" if has_groq else "🔴 Missing")
        st.caption("Embedding Model")
        st.write("🟢 all-MiniLM-L6-v2")

    if not (has_db and has_groq and has_deepgram):
        st.warning("⚠️ Some credentials are missing. Add them to `.env` or Streamlit Secrets.")

    st.markdown("---")
    st.subheader("📚 Indexed Meetings")
    indexed_meetings = get_indexed_meetings()
    if indexed_meetings:
        st.caption(f"Total indexed sessions: {len(indexed_meetings)}")
        for m in indexed_meetings[:10]:
            st.markdown(f"**`{m['id']}`** ({m['chunks']} chunks)")
    else:
        st.caption("No meetings indexed yet in the database.")

    st.markdown("---")
    st.caption("Built with FastAPI, Streamlit, Groq & Deepgram.")

# Halt if configuration failed early
if config_error:
    st.error(f"Configuration error: {config_error}")
    st.info("Please set `DATABASE_URL`, `GROQ_API_KEY`, and `DEEPGRAM_API_KEY` in your `.env` or Streamlit Cloud Secrets.")
    st.stop()

# ==============================================================================
# 5. Main Content Tabs
# ==============================================================================
tabs = st.tabs([
    "📁 Upload Video / Audio", 
    "🔗 Ingest from URL (YouTube)", 
    "💬 Chat with Meetings (RAG)", 
    "🗂️ Browse Meeting Knowledge Base"
])

# ------------------------------------------------------------------------------
# TAB 1: File Upload Pipeline
# ------------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Upload a Video or Audio Recording")
    st.write("Extracts audio via FFmpeg, transcribes using Deepgram Nova-2, generates structured summaries with Groq, and indexes chunks into PostgreSQL.")

    col1, col2 = st.columns([1, 2])
    with col1:
        meeting_id = st.text_input("Meeting ID / Label", placeholder="e.g. sprint-review-nov-11", key="upload_mid")
    with col2:
        uploaded_file = st.file_uploader(
            "Choose a video or audio file", 
            type=["mp4", "mov", "mkv", "avi", "webm", "wav", "mp3", "m4a"],
            help="Files up to 500MB supported"
        )

    if st.button("🚀 Transcribe & Index Recording", type="primary", disabled=not (uploaded_file and meeting_id)):
        save_dir = "uploads_tmp"
        os.makedirs(save_dir, exist_ok=True)
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        temp_file_path = os.path.join(save_dir, f"{uuid.uuid4()}{ext}")
        audio_path = None

        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            with st.status("Processing your recording...", expanded=True) as status:
                # 1. Extract audio if video
                video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
                if ext in video_exts:
                    st.write("🎬 Extracting 16kHz audio with FFmpeg...")
                    audio_path = extract_audio(temp_file_path)
                else:
                    audio_path = temp_file_path

                # 2. Transcribe with Deepgram
                st.write("🎙️ Transcribing audio with Deepgram Nova-2...")
                transcript = transcribe_audio_file(audio_path)
                if not transcript.strip():
                    raise ValueError("No speech detected in this recording.")

                # 3. Summarize with Groq
                st.write("🤖 Generating structured summary with Groq LLM...")
                summary_data = summarize_transcript(transcript)

                # 4. Index in Vector Store
                st.write("🧠 Chunking & indexing embeddings into PostgreSQL...")
                chunk_count = store_transcript(meeting_id, transcript, {"source": "upload", "filename": uploaded_file.name})
                store_summary(meeting_id, summary_data, {"source": "upload", "filename": uploaded_file.name})

                status.update(label="✅ Processing Complete!", state="complete", expanded=False)

            st.success(f"Meeting `{meeting_id}` successfully processed and indexed ({chunk_count} vector chunks)!")

            # Display structured results
            st.markdown("### 📋 Executive Summary")
            st.info(summary_data.get("summary", "No summary generated."))

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🎯 Key Points")
                for pt in summary_data.get("key_points", []):
                    st.markdown(f"- {pt}")
            with c2:
                st.markdown("#### ❓ Follow-up Questions")
                for q in summary_data.get("follow_up_questions", []):
                    st.markdown(f"- {q}")

            with st.expander("📄 View Full Transcript"):
                st.text_area("Transcript", transcript, height=250)

        except Exception as e:
            st.error(f"Error during processing: {e}")
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if audio_path and audio_path != temp_file_path and os.path.exists(audio_path):
                os.remove(audio_path)

# ------------------------------------------------------------------------------
# TAB 2: URL Ingestion Pipeline (YouTube / Web)
# ------------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Process Recording from a URL")
    st.write("Downloads audio directly from YouTube, meeting recording links, or direct video URLs using yt-dlp.")

    url_col1, url_col2 = st.columns([1, 2])
    with url_col1:
        url_meeting_id = st.text_input("Meeting ID / Label", placeholder="e.g. youtube-ai-discussion", key="url_mid")
    with url_col2:
        video_url = st.text_input("URL Link", placeholder="https://www.youtube.com/watch?v=...", key="video_url_val")

    if st.button("🌐 Ingest & Analyze URL", type="primary", disabled=not (url_meeting_id and video_url)):
        downloaded_audio = None
        try:
            with st.status("Fetching and analyzing online media...", expanded=True) as status:
                st.write("⬇️ Downloading audio track via yt-dlp & FFmpeg...")
                downloaded_audio = download_audio_from_url(video_url)

                st.write("🎙️ Transcribing with Deepgram Nova-2...")
                transcript = transcribe_audio_file(downloaded_audio)
                if not transcript.strip():
                    raise ValueError("No speech detected from this URL.")

                st.write("🤖 Generating structured summary with Groq...")
                summary_data = summarize_transcript(transcript)

                st.write("🧠 Storing chunks and summary in PostgreSQL pgvector...")
                chunk_count = store_transcript(url_meeting_id, transcript, {"source": "url", "url": video_url})
                store_summary(url_meeting_id, summary_data, {"source": "url", "url": video_url})

                status.update(label="✅ Processing Complete!", state="complete", expanded=False)

            st.success(f"Meeting `{url_meeting_id}` successfully processed ({chunk_count} vector chunks)!")
            st.markdown("### 📋 Executive Summary")
            st.info(summary_data.get("summary", ""))

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🎯 Key Points")
                for pt in summary_data.get("key_points", []):
                    st.markdown(f"- {pt}")
            with c2:
                st.markdown("#### ❓ Follow-up Questions")
                for q in summary_data.get("follow_up_questions", []):
                    st.markdown(f"- {q}")

            with st.expander("📄 View Full Transcript"):
                st.text_area("Transcript", transcript, height=250)

        except Exception as e:
            st.error(f"Failed to process URL: {e}")
        finally:
            if downloaded_audio and os.path.exists(downloaded_audio):
                os.remove(downloaded_audio)

# ------------------------------------------------------------------------------
# TAB 3: Interactive RAG Chat
# ------------------------------------------------------------------------------
with tabs[2]:
    st.subheader("💬 Ask Your Meetings Anything")
    st.write("Ask natural-language questions. We retrieve semantically relevant chunks from pgvector and formulate answers with Groq.")

    # Filter by specific meeting or all meetings
    all_meetings = [m["id"] for m in get_indexed_meetings()]
    selected_scope = st.selectbox(
        "Search Scope", 
        options=["All Meetings"] + all_meetings,
        index=0,
        help="Select a specific meeting or query across all past meetings."
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display past conversation
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "sources" in message and message["sources"]:
                with st.expander("🔍 View Retrieved Sources"):
                    for s in message["sources"]:
                        st.caption(f"**Meeting:** {s.get('external_id')} | **Score:** {s.get('similarity', 0):.2f}")
                        st.text(s.get("text", ""))

    if user_query := st.chat_input("Ask a question about your meetings..."):
        # Display user question
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # 1. Retrieve relevant chunks using pgvector
        with st.spinner("Searching knowledge base..."):
            raw_results = retrieve(user_query, limit=5)
            
            # Filter if user scoped to a single meeting
            if selected_scope != "All Meetings":
                results = [r for r in raw_results if r.get("external_id") == selected_scope]
            else:
                results = raw_results

            if not results:
                context_str = "No specific meeting context found in database."
            else:
                context_str = "\n\n".join([
                    f"[Meeting: {r.get('external_id')} | Type: {r.get('source_type')}]: {r.get('text')}"
                    for r in results
                ])

            # 2. Synthesize answer with Groq LLM
            groq_client = Groq(api_key=settings.GROQ_API_KEY)
            rag_prompt = f"""You are an intelligent Video & Meeting Assistant. 
Answer the user's question accurately and concisely using ONLY the provided meeting context.
If the information is not in the context, say that the meeting records do not mention it.

Context from Knowledge Base:
{context_str}

User Question: {user_query}
"""
            response = groq_client.chat.completions.create(
                model=settings.GROQ_SUMMARY_MODEL,
                messages=[{"role": "user", "content": rag_prompt}],
                temperature=0.2,
                max_tokens=800,
            )
            answer_text = response.choices[0].message.content

        # Display assistant answer
        with st.chat_message("assistant"):
            st.markdown(answer_text)
            if results:
                with st.expander("🔍 View Retrieved Sources"):
                    for s in results:
                        st.caption(f"**Meeting:** {s.get('external_id')} | **Score:** {s.get('similarity', 0):.2f}")
                        st.text(s.get("text", ""))

        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": answer_text,
            "sources": results
        })

# ------------------------------------------------------------------------------
# TAB 4: Browse Meeting Knowledge Base
# ------------------------------------------------------------------------------
with tabs[3]:
    st.subheader("🗂️ Explore Stored Meetings")
    meetings = get_indexed_meetings()
    if not meetings:
        st.info("No meetings currently found in the PostgreSQL vector database.")
    else:
        chosen_mid = st.selectbox("Select a meeting to inspect:", [m["id"] for m in meetings])
        if chosen_mid:
            data = get_meeting_data(chosen_mid)
            summaries = [row for row in data if row[0] == "summary"]
            transcripts = [row for row in data if row[0] == "transcript"]

            if summaries:
                st.markdown("### 📋 Stored Summary")
                st.info(summaries[0][1])

            st.markdown(f"### 📑 Indexed Chunks ({len(transcripts)} chunks)")
            for i, chunk in enumerate(transcripts[:15]):
                with st.expander(f"Chunk #{i+1}"):
                    st.write(chunk[1])
                    st.caption(f"Metadata: {chunk[2]} | Added: {chunk[3]}")

