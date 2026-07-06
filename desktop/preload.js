// Preload script — runs in a privileged context bridging main and renderer.
// Currently minimal since audio capture + WebSocket happen directly in the
// renderer (both are standard browser APIs, no Node access needed for them).
// Kept as a placeholder for future IPC needs (e.g. system tray controls,
// native audio loopback device selection).

window.addEventListener('DOMContentLoaded', () => {
  console.log('Video RAG Assistant overlay loaded');
});