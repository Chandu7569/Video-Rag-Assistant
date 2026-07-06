from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)
from config import settings


class DeepgramStream:
    """
    Wraps a Deepgram live streaming connection.
    Push raw audio bytes in with `send_audio`; finalized transcript segments
    come out via `on_transcript(text, start_time, end_time)` as they're
    recognized, with timestamps in seconds relative to stream start.
    """

    def __init__(self, on_transcript, encoding: str = None, sample_rate: int = None):
        self.on_transcript = on_transcript
        self.encoding = encoding
        self.sample_rate = sample_rate
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY)
        self.connection = None

    async def start(self):
        self.connection = self.client.listen.asynclive.v("1")

        async def handle_transcript(self_, result, **kwargs):
            if not result.is_final:
                return
            alt = result.channel.alternatives[0]
            text = alt.transcript
            if text.strip():
                start_time = result.start
                end_time = result.start + result.duration
                await self.on_transcript(text, start_time, end_time)

        self.connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)

        options_kwargs = dict(
            model="nova-2",
            language="en-US",
            smart_format=True,
            interim_results=True,
            punctuate=True,
        )
        if self.encoding:
            options_kwargs["encoding"] = self.encoding
        if self.sample_rate:
            options_kwargs["sample_rate"] = self.sample_rate

        options = LiveOptions(**options_kwargs)
        await self.connection.start(options)

    async def send_audio(self, audio_bytes: bytes):
        if self.connection:
            await self.connection.send(audio_bytes)

    async def close(self):
        if self.connection:
            await self.connection.finish()