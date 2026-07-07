import asyncio
import time
from live.deepgram_stream import DeepgramStream
from live.suggester import generate_suggestion
from config import settings


class LiveSession:
    """
    Manages one live call: buffers transcript as it streams in (tracking
    the timestamp where the current buffer started), and periodically
    generates a suggestion once enough new content has arrived.
    """

    def __init__(self, meeting_id: str, on_suggestion, on_transcript_segment=None, encoding: str = None, sample_rate: int = None):
        self.meeting_id = meeting_id
        self.on_suggestion = on_suggestion
        self.on_transcript_segment = on_transcript_segment
        self.unprocessed_buffer = ""
        self.buffer_start_time = None
        self.last_suggestion_time = 0.0
        self.deepgram = DeepgramStream(
            on_transcript=self._handle_transcript,
            encoding=encoding,
            sample_rate=sample_rate,
        )

    async def start(self):
        await self.deepgram.start()

    async def send_audio(self, audio_bytes: bytes):
        await self.deepgram.send_audio(audio_bytes)

    async def _handle_transcript(self, text: str, start_time: float, end_time: float):
        if self.on_transcript_segment:
            await self.on_transcript_segment(text, start_time, end_time)

        if self.buffer_start_time is None:
            self.buffer_start_time = start_time
        self.unprocessed_buffer += " " + text

        now = time.time()
        enough_new_content = len(self.unprocessed_buffer.strip()) >= settings.LIVE_SUGGESTION_MIN_CHARS
        enough_time_passed = (now - self.last_suggestion_time) >= settings.LIVE_SUGGESTION_INTERVAL

        if enough_new_content and enough_time_passed:
            recent = self.unprocessed_buffer.strip()
            recent_start = self.buffer_start_time
            self.unprocessed_buffer = ""
            self.buffer_start_time = None
            self.last_suggestion_time = now

            # Blocking Groq call runs in a thread so it doesn't stall incoming audio
            try:
                suggestion = await asyncio.to_thread(generate_suggestion, recent)
                if suggestion and "no suggestion" not in suggestion.lower():
                    await self.on_suggestion(suggestion, recent_start, end_time)
            except Exception as e:
                print(f"Warning: Failed to generate live suggestion: {e}")

    async def close(self):
        await self.deepgram.close()