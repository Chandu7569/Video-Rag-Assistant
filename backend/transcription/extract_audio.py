import subprocess
import os


def extract_audio(input_path: str, output_path: str = None) -> str:
    """
    Extracts audio from a video (or re-encodes an audio file) into a
    16kHz mono WAV file using ffmpeg — a format Deepgram reliably accepts.

    Requires ffmpeg installed and available on PATH.
    """
    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = base + "_audio.wav"

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000",   # 16kHz sample rate — Deepgram's preferred rate
            "-ac", "1",        # mono
            "-vn",             # strip video stream, audio only
            output_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to extract audio: {result.stderr}")

    return output_path