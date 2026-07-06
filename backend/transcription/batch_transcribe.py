import httpx
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from config import settings


def transcribe_audio_file(file_path: str) -> str:
    """
    Sends a local audio file to Deepgram's pre-recorded (batch) API and
    returns the plain transcript text. This is different from
    live/deepgram_stream.py, which handles real-time streaming audio —
    this one processes a complete file all at once.
    """
    client = DeepgramClient(settings.DEEPGRAM_API_KEY)

    with open(file_path, "rb") as f:
        buffer_data = f.read()

    payload: FileSource = {"buffer": buffer_data}
    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        punctuate=True,
    )

    # deepgram-sdk 3.x uses `.prerecorded.` — `.rest.` is only valid on the
    # newer 7.x SDK line, which is not what's installed here (3.2.7).
    # Use a large timeout (300 seconds) to prevent "The write operation timed out"
    # error when uploading larger video/audio files on slower connections.
    timeout = httpx.Timeout(300.0, connect=10.0)
    response = client.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=timeout)
    transcript = response.results.channels[0].alternatives[0].transcript
    return transcript