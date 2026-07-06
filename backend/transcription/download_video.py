import os
import uuid
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
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    final_path = output_template.replace(".%(ext)s", "") + ".wav"

    if not os.path.exists(final_path):
        raise RuntimeError("Failed to download or convert audio from that URL")

    return final_path