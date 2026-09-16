function updateAudioHealth(audio) {
  if (!audio) return;
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
  text('audio-message', audio.message || 'Voice listener is not running');
  const level = document.getElementById('audio-level');
  if (level) level.value = audio.level_db ?? -70;
  text('audio-device', audio.device ? `${audio.device} · ${audio.echo_cancelled ? 'Voice interruption available' : 'Use Stop speaking or press Enter to interrupt'}` : 'No microphone connected');
  const times = audio.timings || {};
  const timing = (key, label) => times[key] === undefined ? '' : `${label}: ${(times[key] / 1000).toFixed(1)}s`;
  text('audio-timings', [timing('end_of_turn', 'End of sentence'), timing('transcription', 'Transcription'), timing('response', 'Reply'), timing('speech_preparation', 'Voice preparation')].filter(Boolean).join(' · '));
  text('audio-diagnostic', audio.clipping ? 'Microphone input is clipping; lower the input volume.' : audio.diagnostic || '');
}

async function interruptAssistant() {
  window.speechSynthesis?.cancel();
  window.__isAssistantSpeaking = false;
  window.__browserSpeechStartedAt = 0;
  window.__activeUtterance = null;
  try {
    const response = await fetch('/api/voice/interrupt', {method: 'POST'});
    if (!response.ok) throw new Error('Could not stop speech');
  } catch (error) { showToast(error.message); }
}
window.interruptAssistant = interruptAssistant;

async function loadAudioPreferences() {
  try {
    const [status, devices] = await Promise.all([
      fetch('/api/status').then(r => r.json()),
      fetch('/api/audio-devices').then(r => r.json())
    ]);
    const select = document.getElementById('audio-device-select');
    for (const device of devices.devices || []) {
      const option = document.createElement('option');
      option.value = String(device.id);
      option.textContent = device.name;
      select.appendChild(option);
    }
    select.value = status.config.microphone_device == null ? '' : String(status.config.microphone_device);
    document.getElementById('audio-chime').checked = status.config.ready_chime === true;
    document.getElementById('audio-timeout').value = status.config.conversation_timeout_seconds || 30;
    updateAudioHealth(status.voice_audio);
  } catch (error) { console.warn('Audio preferences unavailable', error); }
}

async function saveAudioPreferences() {
  const device = document.getElementById('audio-device-select').value;
  const seconds = Number(document.getElementById('audio-timeout').value);
  if (!Number.isInteger(seconds) || seconds < 5 || seconds > 300) {
    showToast('Choose a reply window between 5 and 300 seconds.');
    return;
  }
  try {
    const response = await fetch('/api/config', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({microphone_device: device === '' ? null : Number(device),
        conversation_timeout_seconds: seconds, ready_chime: document.getElementById('audio-chime').checked})
    });
    if (!response.ok) throw new Error('Could not save listening preferences');
    showToast('Listening preferences saved. Restart the assistant to apply them.');
  } catch (error) { showToast(error.message); }
}
loadAudioPreferences();
