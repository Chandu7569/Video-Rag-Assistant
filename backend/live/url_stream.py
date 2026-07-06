import asyncio
import subprocess
import yt_dlp


def get_direct_stream_url(url: str) -> str:
    """
    Resolves a page URL (e.g. a YouTube Live link) to a direct, playable
    stream URL that ffmpeg can read from continuously.
    """
    ydl_opts = {"quiet": True, "format": "bestaudio/best"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]


class UrlAudioStreamer:
    """
    Reads a LIVE audio stream from a URL (via ffmpeg) and pushes raw PCM
    chunks to a callback — feeding the same live pipeline
    (Deepgram -> retrieval -> Groq) that the desktop mic capture uses,
    just with a live stream URL as the audio source instead of a
    microphone.
    """

    def __init__(self, url: str, on_audio_chunk):
        self.url = url
        self.on_audio_chunk = on_audio_chunk
        self.process = None
        self._running = False

    async def start(self):
        stream_url = await asyncio.to_thread(get_direct_stream_url, self.url)

        # ffmpeg reads the live stream and outputs raw 16-bit PCM audio,
        # 16kHz mono — matched explicitly in deepgram_stream.py's
        # LiveOptions (encoding="linear16", sample_rate=16000).
        self.process = subprocess.Popen(
            [
                "ffmpeg", "-i", stream_url,
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                "-loglevel", "quiet",
                "-",
            ],
            stdout=subprocess.PIPE,
        )

        self._running = True
        asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        chunk_size = 4096
        while self._running and self.process:
            chunk = await asyncio.to_thread(self.process.stdout.read, chunk_size)
            if not chunk:
                break
            await self.on_audio_chunk(chunk)
        self._running = False

    async def stop(self):
        self._running = False
        if self.process:
            self.process.terminate()
            self.process = None