# Video RAG Assistant

A real-time video speech-to-text, vector retrieval (RAG), summarization, and AI-driven suggestion assistant. This application features a **FastAPI backend** coupled with an **Electron desktop app**.

---

## Features
- **Real-Time Streaming**: Uses Deepgram's WebSocket API for instantaneous live transcription.
- **RAG & Vector Search**: Implements local HuggingFace embeddings (`all-MiniLM-L6-v2`) and PostgreSQL (`pgvector`) to index and retrieve contextually relevant transcripts and documents.
- **AI-Powered Suggestions**: Leverages Groq's fast LLM APIs to generate dynamic live suggestions during calls or meetings.
- **Meeting Summarization**: Automatically produces structured meeting summaries.

---

## Project Structure
```text
├── backend/            # FastAPI Python server (RAG, database integrations, streaming endpoint)
├── db/                 # Database setup and migrations
├── desktop/            # Electron-based desktop frontend
├── docs/               # Project plans and design documentation
└── start-all.bat       # Startup script to launch both services simultaneously
```

---

## Prerequisites
Before you start, make sure you have the following installed on your machine:
1. **Python 3.10+**
2. **Node.js (v18+) & npm**
3. **PostgreSQL** with the `pgvector` extension enabled (e.g., standard local Postgres or a cloud database like Supabase).
4. **API Keys**:
   - A [Groq API Key](https://console.groq.com/)
   - A [Deepgram API Key](https://console.deepgram.com/)

---

## Installation & Setup

### 1. Database Setup
Ensure you have a PostgreSQL database running, then execute the schema script to create the necessary tables and enable `pgvector`:
```bash
psql -U your_postgres_user -d your_database_name -f db/scheme.sql
```
*Note: If using Supabase, you can copy the contents of `db/scheme.sql` and run it in the SQL Editor.*

### 2. Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create your `.env` file by copying the template:
   ```bash
   copy .env.example .env
   ```
3. Open `.env` and fill in your database connection string and API keys:
   ```env
   DATABASE_URL=postgresql://your_db_user:your_db_password@your_db_host:5432/your_db_name
   GROQ_API_KEY=your-groq-key
   DEEPGRAM_API_KEY=your-deepgram-key
   ```
4. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows (CMD/PowerShell):
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
5. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Desktop Application Setup
1. Navigate to the `desktop` directory:
   ```bash
   cd ../desktop
   ```
2. Install the Node dependencies:
   ```bash
   npm install
   ```

---

## Running the Application

### The Easy Way (Windows batch script)
Run the following command from the root directory of the project in Windows PowerShell:
```powershell
start-all.bat
```
*(In standard Command Prompt, you can run `start-all.bat` directly).*

This script will automatically:
1. Start the FastAPI server (running on `http://127.0.0.1:8000`).
2. Wait 3 seconds for the backend to initialize.
3. Start the Electron desktop app.

---

### Running Manually

#### Start Backend:
```bash
cd backend
# Activate virtual environment
.\venv\Scripts\activate
# Start Uvicorn
uvicorn main:app --reload
```

#### Start Desktop App:
```bash
cd desktop
npm start
```
