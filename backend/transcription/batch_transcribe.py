import httpx
import os
import glob
import subprocess
from deepgram import DeepgramClient
try:
    from deepgram import PrerecordedOptions, FileSource
except (ImportError, AttributeError):
    try:
        from deepgram.clients.prerecorded.v1.options import PrerecordedOptions
        from deepgram.clients.prerecorded.v1.types import FileSource
    except (ImportError, AttributeError):
        class PrerecordedOptions(dict):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
        FileSource = dict
from config import settings


def transcribe_audio_file(file_path: str) -> str:
    """
    Sends a local audio file to Deepgram's pre-recorded (batch) API and
    returns the plain transcript text. Splits the audio into chunks to
    prevent 504 Gateway Timeouts on long videos.
    """
    client = DeepgramClient(settings.DEEPGRAM_API_KEY)

    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        punctuate=True,
    )
    timeout = httpx.Timeout(3000.0, connect=10.0)

    # Split the file into 10-minute (600s) chunks to prevent 504 timeouts
    base, ext = os.path.splitext(file_path)
    chunk_pattern = f"{base}_chunk_%03d{ext}"
    
    # We use `-c copy` to avoid re-encoding, making the split very fast
    subprocess.run([
        "ffmpeg", "-y", "-i", file_path,
        "-f", "segment", "-segment_time", "600",
        "-c", "copy", chunk_pattern
    ], check=True, capture_output=True)

    chunk_files = sorted(glob.glob(f"{base}_chunk_*{ext}"))
    if not chunk_files:
        # Fallback if ffmpeg failed to create chunks for some reason
        chunk_files = [file_path]
    
    full_transcript = []
    try:
        for chunk_file in chunk_files:
            with open(chunk_file, "rb") as f:
                buffer_data = f.read()
            
            payload: FileSource = {"buffer": buffer_data}
            response = client.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=timeout)
            transcript_part = response.results.channels[0].alternatives[0].transcript
            if transcript_part:
                full_transcript.append(transcript_part.strip())
    finally:
        # Clean up chunk files (don't delete the original file_path)
        for chunk_file in chunk_files:
            if chunk_file != file_path and os.path.exists(chunk_file):
                os.remove(chunk_file)

    return " ".join(full_transcript)