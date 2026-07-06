FROM python:3.11-slim

# System dependencies:
# - ffmpeg: audio/video extraction (extract_audio.py, download_video.py)
# - deno: JS runtime yt-dlp needs for reliable YouTube extraction
# - curl/unzip: needed to install deno
RUN apt-get update && apt-get install -y ffmpeg curl unzip \
    && curl -fsSL https://deno.land/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/deno \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT dynamically; must bind to it, not a hardcoded port
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}