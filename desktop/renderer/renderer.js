// ============================================================
// IMPORTANT: after deploying your backend to Render, replace the
// value below with your actual Render URL (without https:// or
// trailing slash), e.g. "video-rag-backend.onrender.com"
// ============================================================
const BACKEND_HOST = '127.0.0.1:8000';
const IS_LOCAL = BACKEND_HOST.includes('localhost') || BACKEND_HOST.includes('127.0.0.1');

const BACKEND_HTTP_BASE = IS_LOCAL ? `http://${BACKEND_HOST}` : `https://${BACKEND_HOST}`;
const BACKEND_WS_BASE = IS_LOCAL ? `ws://${BACKEND_HOST}/ws/live` : `wss://${BACKEND_HOST}/ws/live`;

// ---- DOM references (declared up front so no element is used before it exists) ----
const meetingIdInput = document.getElementById('meetingId');
const connectBtn = document.getElementById('connectBtn');
const statusEl = document.getElementById('status');
const suggestionsEl = document.getElementById('suggestions');
const emptyState = document.getElementById('empty-state');

const uploadMeetingIdInput = document.getElementById('uploadMeetingId');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatusEl = document.getElementById('uploadStatus');
const uploadResultEl = document.getElementById('uploadResult');

const urlMeetingIdInput = document.getElementById('urlMeetingId');
const videoUrlInput = document.getElementById('videoUrlInput');
const urlBtn = document.getElementById('urlBtn');
const urlStatusEl = document.getElementById('urlStatus');
const urlResultEl = document.getElementById('urlResult');

const liveUrlBtn = document.getElementById('liveUrlBtn');
const liveUrlStatusEl = document.getElementById('liveUrlStatus');

const summarySection = document.getElementById('summarySection');
const summaryContentEl = document.getElementById('summaryContent');
const transcriptSection = document.getElementById('transcriptSection');
const transcriptContentEl = document.getElementById('transcriptContent');

let socket = null;
let mediaRecorder = null;
let isListening = false;
let liveUrlSocket = null;
let isLiveUrlActive = false;

// ---- Shared helpers ----

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatTime(seconds) {
  if (seconds === undefined || seconds === null) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function setStatus(text, className) {
  statusEl.textContent = text;
  statusEl.className = className || '';
}

function setUploadStatus(text, className) {
  uploadStatusEl.textContent = text;
  uploadStatusEl.className = className || '';
}

function setUrlStatus(text, className) {
  urlStatusEl.textContent = text;
  urlStatusEl.className = className || '';
}

function setLiveUrlStatus(text, className) {
  liveUrlStatusEl.textContent = text;
  liveUrlStatusEl.className = className || '';
}

// Renders a summary object into a small inline result block (used under
// each individual action button, e.g. upload/url), AND into the big
// central Summary card that's the main focal point of the new layout.
function renderSummaryBlock(summary) {
  const keyPointsHtml = summary.key_points.map((p) => `<li>${escapeHtml(p)}</li>`).join('');
  const questionsHtml = summary.follow_up_questions.map((q) => `<li>${escapeHtml(q)}</li>`).join('');
  return `
    <h4>Summary</h4>
    <p>${escapeHtml(summary.summary)}</p>
    <h4>Key Points</h4>
    <ul>${keyPointsHtml}</ul>
    <h4>Follow-up Questions</h4>
    <ul>${questionsHtml}</ul>
  `;
}

function populateSummaryCard(summary) {
  summarySection.classList.remove('is-empty');
  summaryContentEl.classList.remove('expanded');
  summaryContentEl.innerHTML = renderSummaryBlock(summary);
}

// Shows a full transcript as one block (used for upload/URL batch results,
// where we only get a single transcript string back, not per-line timing).
function populateTranscriptBlock(transcriptText) {
  transcriptSection.classList.remove('is-empty');
  transcriptContentEl.innerHTML = `<div class="line"><div class="text">${escapeHtml(transcriptText)}</div></div>`;
}

// Appends one timestamped line (used for live sessions, mic or URL, where
// segments arrive incrementally as the call/stream progresses).
function appendTranscriptLine(text, startTime) {
  transcriptSection.classList.remove('is-empty');
  const placeholder = transcriptContentEl.querySelector('.line .text[data-placeholder]');
  if (placeholder) transcriptContentEl.innerHTML = '';

  const line = document.createElement('div');
  line.className = 'line';
  const tsHtml = startTime !== undefined && startTime !== null
    ? `<div class="ts">${formatTime(startTime)}</div>`
    : '';
  line.innerHTML = `${tsHtml}<div class="text">${escapeHtml(text)}</div>`;
  transcriptContentEl.appendChild(line);
}

function addSuggestion(text, startTime, endTime) {
  if (emptyState) emptyState.remove();

  const div = document.createElement('div');
  div.className = 'suggestion';

  const timeLabel = (startTime !== undefined && startTime !== null)
    ? `${formatTime(startTime)} – ${formatTime(endTime)}`
    : new Date().toLocaleTimeString();

  div.innerHTML = `<div class="time">${timeLabel}</div>${escapeHtml(text)}`;
  suggestionsEl.prepend(div); // newest suggestion on top
}

// ---- Live mic-based session (Start Listening) ----

async function startListening() {
  const meetingId = meetingIdInput.value.trim();
  if (!meetingId) {
    setStatus('Enter a meeting ID first', 'error');
    connectBtn.disabled = false;
    return;
  }

  // Request microphone access.
  // NOTE: this captures your MIC only, not system/call audio. To capture
  // the other person's voice from a call app too, you'll need a virtual
  // audio loopback device (e.g. BlackHole on macOS, VB-Cable on Windows)
  // set as an additional input, mixed in here.
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    setStatus('Microphone access denied', 'error');
    connectBtn.disabled = false;
    console.error(err);
    return;
  }

  socket = new WebSocket(`${BACKEND_WS_BASE}/${encodeURIComponent(meetingId)}`);
  socket.binaryType = 'arraybuffer';

  socket.onopen = () => {
    setStatus('Connected — listening...', 'connected');
    isListening = true;
    document.body.classList.add('is-listening');
    connectBtn.setAttribute('aria-label', 'Stop listening');
    connectBtn.title = 'Stop listening';
    connectBtn.disabled = false;

    // MediaRecorder captures audio as webm/opus chunks and streams them
    // to the backend every second. NOTE: Deepgram's live API needs to be
    // configured to match this container/encoding — if you see transcription
    // errors, check live/deepgram_stream.py's LiveOptions against the
    // encoding MediaRecorder produces here (webm/opus by default).
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

    mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
        const buffer = await event.data.arrayBuffer();
        socket.send(buffer);
      }
    };

    mediaRecorder.start(1000); // emit a chunk every 1 second
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'suggestion') {
        addSuggestion(data.text, data.start_time, data.end_time);
      } else if (data.type === 'transcript') {
        appendTranscriptLine(data.text, data.start_time);
      }
    } catch (err) {
      console.error('Failed to parse message from server:', err);
    }
  };

  socket.onerror = () => {
    setStatus('Connection error', 'error');
  };

  socket.onclose = () => {
    setStatus('Disconnected', '');
    stopListening(stream);
  };
}

function stopListening(stream) {
  isListening = false;
  document.body.classList.remove('is-listening');
  connectBtn.setAttribute('aria-label', 'Start listening');
  connectBtn.title = 'Start listening';
  connectBtn.disabled = false;

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }
}

connectBtn.addEventListener('click', () => {
  if (isListening) {
    connectBtn.disabled = true;
    setStatus('Stopping...', '');
    socket.close(); // triggers onclose -> stopListening cleanup
  } else {
    connectBtn.disabled = true;
    setStatus('Connecting...', '');
    startListening();
  }
});

// ---- File upload (video/audio -> transcribe + summarize) ----

// Show the chosen filename in the drop zone
fileInput.addEventListener('change', () => {
  const filenameLabel = document.getElementById('filenameLabel');
  if (filenameLabel) {
    filenameLabel.textContent = fileInput.files[0] ? fileInput.files[0].name : '';
  }
});

uploadBtn.addEventListener('click', async () => {
  const meetingId = uploadMeetingIdInput.value.trim();
  const file = fileInput.files[0];

  if (!meetingId) {
    setUploadStatus('Enter a meeting ID first', 'error');
    return;
  }
  if (!file) {
    setUploadStatus('Choose a video or audio file first', 'error');
    return;
  }

  uploadBtn.disabled = true;
  uploadResultEl.innerHTML = '';
  setUploadStatus('Uploading and processing... this can take a minute for longer recordings', '');

  const formData = new FormData();
  formData.append('file', file);
  formData.append('meeting_id', meetingId);

  try {
    const response = await fetch(`${BACKEND_HTTP_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();

    if (data.status === 'ok') {
      setUploadStatus(
        `Done — ${data.transcript_chunks_indexed} transcript chunks indexed`,
        'success'
      );
      uploadResultEl.innerHTML = renderSummaryBlock(data.summary);
      populateSummaryCard(data.summary);
      if (data.transcript) populateTranscriptBlock(data.transcript);
    } else {
      setUploadStatus(data.message || 'Something went wrong', 'error');
    }
  } catch (err) {
    console.error(err);
    setUploadStatus('Upload failed — is the backend running?', 'error');
  } finally {
    uploadBtn.disabled = false;
  }
});

// ---- Summarize from a URL — finished recording (YouTube, Zoom recording link, etc.) ----

urlBtn.addEventListener('click', async () => {
  const meetingId = urlMeetingIdInput.value.trim();
  const url = videoUrlInput.value.trim();

  if (!meetingId) {
    setUrlStatus('Enter a meeting ID first', 'error');
    return;
  }
  if (!url) {
    setUrlStatus('Paste a video or recording URL first', 'error');
    return;
  }

  urlBtn.disabled = true;
  urlResultEl.innerHTML = '';
  setUrlStatus('Fetching and processing... this can take a minute or more', '');

  try {
    const response = await fetch(`${BACKEND_HTTP_BASE}/upload-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, meeting_id: meetingId }),
    });
    const data = await response.json();

    if (data.status === 'ok') {
      setUrlStatus(
        `Done — ${data.transcript_chunks_indexed} transcript chunks indexed`,
        'success'
      );
      urlResultEl.innerHTML = renderSummaryBlock(data.summary);
      populateSummaryCard(data.summary);
      if (data.transcript) populateTranscriptBlock(data.transcript);
    } else {
      setUrlStatus(data.message || 'Something went wrong', 'error');
    }
  } catch (err) {
    console.error(err);
    setUrlStatus('Request failed — is the backend running?', 'error');
  } finally {
    urlBtn.disabled = false;
  }
});

// ---- Live summary from an ONGOING stream URL (not a finished recording) ----

function startLiveUrlSession() {
  const meetingId = urlMeetingIdInput.value.trim();
  const url = videoUrlInput.value.trim();

  if (!meetingId || !url) {
    setLiveUrlStatus('Enter a meeting ID and URL above first', 'error');
    liveUrlBtn.disabled = false;
    return;
  }

  const wsProtocol = IS_LOCAL ? 'ws://' : 'wss://';
  liveUrlSocket = new WebSocket(`${wsProtocol}${BACKEND_HOST}/ws/live-url/${encodeURIComponent(meetingId)}`);

  liveUrlSocket.onopen = () => {
    liveUrlSocket.send(JSON.stringify({ url }));
    setLiveUrlStatus('Connected — monitoring live stream...', 'connected');
    isLiveUrlActive = true;
    liveUrlBtn.querySelector('.btn-label').textContent = 'Stop Live Summary';
    liveUrlBtn.classList.add('is-active');
    liveUrlBtn.disabled = false;
  };

  liveUrlSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'suggestion') {
        addSuggestion(data.text, data.start_time, data.end_time);
      } else if (data.type === 'transcript') {
        appendTranscriptLine(data.text, data.start_time);
      } else if (data.type === 'error') {
        setLiveUrlStatus(data.text, 'error');
      }
    } catch (err) {
      console.error('Failed to parse live-url message:', err);
    }
  };

  liveUrlSocket.onerror = () => setLiveUrlStatus('Connection error', 'error');

  liveUrlSocket.onclose = () => {
    isLiveUrlActive = false;
    liveUrlBtn.querySelector('.btn-label').textContent = 'Start Live Summary (ongoing stream)';
    liveUrlBtn.classList.remove('is-active');
    liveUrlBtn.disabled = false;
    setLiveUrlStatus('Disconnected', '');
  };
}

liveUrlBtn.addEventListener('click', () => {
  if (isLiveUrlActive) {
    liveUrlBtn.disabled = true;
    setLiveUrlStatus('Stopping...', '');
    liveUrlSocket.close();
  } else {
    liveUrlBtn.disabled = true;
    setLiveUrlStatus('Connecting...', '');
    startLiveUrlSession();
  }
});