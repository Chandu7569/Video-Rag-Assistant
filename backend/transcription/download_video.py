import os
import uuid
import time
import yt_dlp


def download_audio_from_url(url: str, output_dir: str = "uploads_tmp") -> str:
    """
    Downloads the best available audio track from a video URL (YouTube,
    direct file links, and many meeting-recording hosts) using yt-dlp,
    converts it to WAV via ffmpeg, and returns the local file path.

    Requires ffmpeg installed (same requirement as extract_audio.py).
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, f"{uuid.uuid4()}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"]
            }
        },
        "quiet": True,
        "noplaylist": True,
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Warning: yt-dlp download failed (attempt {attempt + 1}/{max_retries}), retrying in 2s: {e}")
                time.sleep(2)
            else:
                raise RuntimeError(f"Failed to download audio after {max_retries} attempts: {e}") from e

    final_path = output_template.replace(".%(ext)s", "") + ".wav"

    if not os.path.exists(final_path):
        raise RuntimeError("Failed to download or convert audio from that URL")

    return final_path