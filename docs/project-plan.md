video-rag-assistant/
├── db/
│   ├── schema.sql
│   └── upgrade_index.sql
│
├── backend/
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── venv/
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   │
│   ├── rag/
│   │   ├── chunker.py
│   │   ├── embed.py
│   │   ├── vector_store.py
│   │   └── retrieve.py
│   │
│   ├── summarizer/
│   │   ├── post_call.py
│   │   ├── store.py
│   │   └── run.py
│   │
│   ├── live/
│   │   ├── deepgram_stream.py
│   │   ├── suggester.py
│   │   ├── session.py
│   │   └── url_stream.py
│   │
│   └── transcription/
│       ├── extract_audio.py
│       ├── batch_transcribe.py
│       └── download_video.py
│
└── desktop/
    ├── package.json
    ├── main.js
    ├── preload.js
    │
    └── renderer/
        ├── index.html
        └── renderer.js