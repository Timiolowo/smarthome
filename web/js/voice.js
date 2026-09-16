/* ==========================================================================
   VOICE — Speech Recognition, Synthesis, Live Listen & Mic Permissions
   ========================================================================== */

let isVoiceOutputEnabled = localStorage.getItem('smarthome_voice_reply') !== 'false';
let isContinuousLiveMode = false;
let isLiveListenActive = false;
let userExplicitlyStopped = false;
let globalSpeechRec = null;
let speechTimerInterval = null;
let terminalVoiceMode = 'wake';
window.__isAssistantSpeaking = false;
window.__activeUtterance = null;

// Safari WebKit Audio & Speech Synthesis Unlocker
function primeSafariAudioContext() {
  if (window.__speechContextPrimed) return;
  window.__speechContextPrimed = true;
  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.resume();
      const primeUtterance = new SpeechSynthesisUtterance(' ');
      primeUtterance.volume = 0.01;
      primeUtterance.rate = 2.0;
      window.speechSynthesis.speak(primeUtterance);
    } catch(e) {}
  }
}
document.addEventListener('click', primeSafariAudioContext, { passive: true });
document.addEventListener('touchstart', primeSafariAudioContext, { passive: true });
document.addEventListener('keydown', primeSafariAudioContext, { passive: true });

function toggleVoiceOutput() {
  isVoiceOutputEnabled = !isVoiceOutputEnabled;
  localStorage.setItem('smarthome_voice_reply', isVoiceOutputEnabled);
  updateVoiceOutputUI();
  if (typeof showSonner === 'function') {
    showSonner('Voice Output ' + (isVoiceOutputEnabled ? 'Enabled' : 'Disabled'), isVoiceOutputEnabled ? 'AI will speak replies aloud.' : 'Text-only mode.');
  }
}
window.toggleVoiceOutput = toggleVoiceOutput;

function updateVoiceOutputUI() {
  const icon = document.getElementById('voice-output-icon');
  const label = document.getElementById('voice-output-label');
  if (icon) {
    icon.innerHTML = isVoiceOutputEnabled
      ? `<svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`
      : `<svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>`;
  }
  if (label) label.textContent = isVoiceOutputEnabled ? 'Voice: ON' : 'Voice: OFF';
}

function toggleContinuousLiveMode() {
  isContinuousLiveMode = !isContinuousLiveMode;
  localStorage.setItem('smarthome_continuous_listen', isContinuousLiveMode);
  updateContinuousModeUI();
  if (typeof showSonner === 'function') {
    showSonner(
      isContinuousLiveMode ? 'Hands-Free Dialogue: ON' : 'Hands-Free Dialogue: OFF',
      isContinuousLiveMode ? 'Assistant will automatically listen for your next command after speaking.' : 'Manual push-to-talk mode active.'
    );
  }
}
window.toggleContinuousLiveMode = toggleContinuousLiveMode;

function updateContinuousModeUI() {
  const btn = document.getElementById('btn-continuous-mode-toggle');
  const label = document.getElementById('continuous-mode-label');
  if (btn) {
    if (isContinuousLiveMode) {
      btn.classList.add('btn-primary');
      btn.classList.remove('btn-outline');
    } else {
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-outline');
    }
  }
  if (label) {
    label.textContent = isContinuousLiveMode ? 'Hands-Free: ON' : 'Hands-Free: OFF';
  }
}

function cleanSpokenText(text) {
  if (!text) return '';
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/#+\s*/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[•\-\*]\s+/g, '')
    .replace(/[_~>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function getBestNaturalVoice() {
  if (!('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices() || [];
  if (!voices.length) return null;

  const savedVoiceName = localStorage.getItem('smarthome_selected_voice');
  if (savedVoiceName) {
    const matched = voices.find(v => v.name === savedVoiceName);
    if (matched) return matched;
  }

  const prioritized = [
    'Samantha (Enhanced)',
    'Siri',
    'Daniel (Enhanced)',
    'Karen (Enhanced)',
    'Samantha',
    'Daniel',
    'Karen',
    'Victoria',
    'Alex',
    'Ava',
    'Allison',
    'Google US English',
    'Google UK English Female'
  ];

  for (const name of prioritized) {
    const found = voices.find(v => v.name.toLowerCase().includes(name.toLowerCase()) && v.lang.startsWith('en'));
    if (found) return found;
  }

  return voices.find(v => v.lang === 'en-US') ||
         voices.find(v => v.lang.startsWith('en')) ||
         voices[0];
}

function populateVoiceDropdown() {
  const select = document.getElementById('cfg-browser-voice');
  if (!select || !('speechSynthesis' in window)) return;
  const voices = window.speechSynthesis.getVoices() || [];
  if (!voices.length) return;

  const savedVoice = localStorage.getItem('smarthome_selected_voice') || '';
  const currentOptions = Array.from(select.options).map(o => o.value);

  // Filter primarily English voices first
  const enVoices = voices.filter(v => v.lang.startsWith('en'));
  const otherVoices = voices.filter(v => !v.lang.startsWith('en'));

  let html = `<option value="">Auto-Detect Best Natural Voice (${getBestNaturalVoice()?.name || 'Samantha'})</option>`;
  if (enVoices.length) {
    html += `<optgroup label="English Voices (Mac & Browser)">`;
    enVoices.forEach(v => {
      const selected = (v.name === savedVoice) ? 'selected' : '';
      html += `<option value="${v.name}" ${selected}>${v.name} (${v.lang})</option>`;
    });
    html += `</optgroup>`;
  }
  if (otherVoices.length) {
    html += `<optgroup label="Other International Voices">`;
    otherVoices.forEach(v => {
      const selected = (v.name === savedVoice) ? 'selected' : '';
      html += `<option value="${v.name}" ${selected}>${v.name} (${v.lang})</option>`;
    });
    html += `</optgroup>`;
  }
  select.innerHTML = html;
}

function handleVoiceSelectionChange(voiceName) {
  if (voiceName) {
    localStorage.setItem('smarthome_selected_voice', voiceName);
    showSonner('Voice Selected', `AI Voice set to: ${voiceName}`);
  } else {
    localStorage.removeItem('smarthome_selected_voice');
    showSonner('Voice Mode', 'Auto-detecting best natural Mac voice');
  }
  // Sync to backend config.json
  fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({voice_name: voiceName || 'default'})
  }).catch(() => {});
}
window.handleVoiceSelectionChange = handleVoiceSelectionChange;

function testSelectedVoice() {
  const voice = getBestNaturalVoice();
  const name = voice ? voice.name : 'Default Voice';
  showSonner('Testing Voice', `Speaking with ${name}...`);
  speakWithBrowserVoice(`Hello Timilehin. This is the ${name} voice speaking. Ready to assist your smart home.`);
}
window.testSelectedVoice = testSelectedVoice;

function speakWithBrowserVoice(rawText, onFinish) {
  if (!isVoiceOutputEnabled || !('speechSynthesis' in window)) {
    if (onFinish) onFinish();
    return;
  }

  const text = cleanSpokenText(rawText);
  if (!text) {
    if (onFinish) onFinish();
    return;
  }

  try {
    window.__isAssistantSpeaking = true;
    window.__browserSpeechStartedAt = performance.now();
    if (speechTimerInterval) clearInterval(speechTimerInterval);

    // Stop speech recognition immediately while the assistant speaks so it doesn't self-transcribe
    if (globalSpeechRec) {
      try { globalSpeechRec.stop(); } catch(e){}
    }

    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
      window.speechSynthesis.cancel();
    }
    window.speechSynthesis.resume();

    const utterance = new SpeechSynthesisUtterance(text);
    window.__activeUtterance = utterance; // Prevent WebKit GC from destroying utterance

    const voice = getBestNaturalVoice();
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang || 'en-US';
    } else {
      utterance.lang = 'en-US';
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    // Visual feedback on Live Display Orb & Navbar
    const orb = document.getElementById('live-ai-orb');
    const orbState = document.getElementById('live-orb-state-text');
    if (orb) {
      orb.classList.remove('idle', 'listening');
      orb.classList.add('speaking');
    }
    if (orbState) orbState.textContent = 'Speaking response...';
    if (window.tarsController) {
      window.tarsController.setState('speaking');
    }

    // Safari WebKit 15s audio freeze workaround
    speechTimerInterval = setInterval(() => {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      } else {
        clearInterval(speechTimerInterval);
      }
    }, 10000);

    let finished = false;
    const cleanup = () => {
      if (finished) return;
      finished = true;
      window.__isAssistantSpeaking = false;
      window.__browserSpeechStartedAt = 0;
      window.__activeUtterance = null;
      if (speechTimerInterval) {
        clearInterval(speechTimerInterval);
        speechTimerInterval = null;
      }
      if (orb) {
        orb.classList.remove('speaking');
        orb.classList.add('idle');
      }
      if (orbState) orbState.textContent = 'Standby • Listening...';
      if (window.tarsController && !isLiveListenActive) {
        window.tarsController.setState('standby');
      }

      if (onFinish) onFinish();
    };

    utterance.onend = () => {
      cleanup();
    };
    utterance.onerror = (e) => {
      console.warn("Speech synthesis notice:", e);
      cleanup();
    };

    // Safety timeout in case Safari drops onend
    const estimatedDurationMs = Math.max(3500, (text.length / 12) * 1000);
    setTimeout(() => {
      if (window.__isAssistantSpeaking && !window.speechSynthesis.speaking) {
        cleanup();
      }
    }, estimatedDurationMs + 2000);

    window.speechSynthesis.speak(utterance);
    window.speechSynthesis.resume();
  } catch (err) {
    console.warn("Browser speech synthesis error:", err);
    window.__isAssistantSpeaking = false;
    window.__browserSpeechStartedAt = 0;
    if (speechTimerInterval) clearInterval(speechTimerInterval);
    if (onFinish) onFinish();
  }
}
window.speakWithBrowserVoice = speakWithBrowserVoice;

// Load voices when available in Safari & Chrome
if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
    populateVoiceDropdown();
  };
}

async function setTerminalVoiceMode(mode) {
  if (mode !== 'live' && typeof window.interruptAssistant === 'function') {
    await window.interruptAssistant();
  }
  const switchLive = document.getElementById('switch-tars-live-listen');
  const switchMic = document.getElementById('switch-tars-mic');
  const controls = [
    document.getElementById('btn-tars-live-listen'),
    document.getElementById('btn-tars-mic-off'),
    document.getElementById('btn-chat-live-listen'),
    document.getElementById('btn-chat-mic')
  ].filter(Boolean);
  controls.forEach(control => { control.disabled = true; });
  if (switchLive) switchLive.classList.add('disabled');
  if (switchMic) switchMic.classList.add('disabled');
  try {
    const res = await fetch('/api/voice/listening', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Unable to change listening mode');
    updateTerminalVoiceUI(data.voice_mode);
  } catch (error) {
    updateTerminalVoiceUI('offline');
    if (typeof showSonner === 'function') {
      showSonner('Voice Control Unavailable', error.message);
    }
  } finally {
    const unavailable = terminalVoiceMode === 'offline' || terminalVoiceMode === 'stopped';
    controls.forEach(control => { control.disabled = unavailable; });
    if (switchLive) {
      switchLive.classList.toggle('disabled', unavailable);
      switchLive.setAttribute('aria-disabled', unavailable ? 'true' : 'false');
    }
    if (switchMic) {
      switchMic.classList.toggle('disabled', unavailable);
      switchMic.setAttribute('aria-disabled', unavailable ? 'true' : 'false');
    }
  }
}

function toggleLiveVoiceListen() {
  setTerminalVoiceMode(terminalVoiceMode === 'live' ? 'wake' : 'live');
}
window.toggleLiveVoiceListen = toggleLiveVoiceListen;

function toggleTerminalMicrophone() {
  setTerminalVoiceMode(terminalVoiceMode === 'off' ? 'wake' : 'off');
}
window.toggleTerminalMicrophone = toggleTerminalMicrophone;

function updateTerminalVoiceUI(mode) {
  terminalVoiceMode = mode || 'wake';
  const asstName = (window.cachedStatus?.assistant?.name || window.cachedStatus?.config?.assistant_name || 'Nova').toUpperCase();
  const labels = {
    wake: `WAITING FOR "${asstName}"`,
    live: 'LIVE LISTENING',
    off: 'MICROPHONE OFF',
    starting: 'BACKEND STARTING',
    stopped: 'BACKEND OFFLINE',
    offline: 'BACKEND OFFLINE'
  };
  const statusLabel = document.getElementById('terminal-voice-mode');
  const liveBadge = document.getElementById('tars-live-listen-badge');
  const liveButton = document.getElementById('btn-tars-live-listen');
  const micOffButton = document.getElementById('btn-tars-mic-off');
  const switchLive = document.getElementById('switch-tars-live-listen');
  const switchMic = document.getElementById('switch-tars-mic');
  const chatLabel = document.getElementById('live-listen-label');
  const chatButton = document.getElementById('btn-chat-live-listen');
  const chatMic = document.getElementById('btn-chat-mic');
  const backendUnavailable = terminalVoiceMode === 'offline' || terminalVoiceMode === 'stopped';

  const isError = window.cachedStatus?.voice_audio?.state === 'ERROR' ||
                  window.cachedStatus?.assistant_runtime?.state === 'ERROR' ||
                  (window.cachedStatus?.voice_audio?.message && window.cachedStatus.voice_audio.message.toLowerCase().includes('blocked by macos'));

  if (statusLabel) {
    if (isError) {
      statusLabel.classList.add('error');
      statusLabel.textContent = window.cachedStatus.voice_audio.message || 'MICROPHONE BLOCKED / ERROR';
    } else {
      const isAssistantSpeaking = Boolean(window.__isAssistantSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking));
      const isTranscribing = Boolean(window.browserVoiceSession && window.browserVoiceSession.processing);
      const isUserSpeaking = Boolean(window.browserVoiceSession && window.browserVoiceSession.capturing);

      statusLabel.classList.remove('error');
      if (isAssistantSpeaking) {
        statusLabel.textContent = 'SPEAKING RESPONSE...';
      } else if (isTranscribing) {
        statusLabel.textContent = 'TRANSCRIBING & THINKING...';
      } else if (isUserSpeaking) {
        statusLabel.textContent = 'HEARING YOU...';
      } else {
        statusLabel.textContent = labels[terminalVoiceMode] || labels.wake;
      }
    }
  }
  if (liveBadge) liveBadge.textContent = terminalVoiceMode === 'live' ? 'STOP' : 'START';
  if (chatLabel) chatLabel.textContent = terminalVoiceMode === 'live' ? 'Stop Live Listening' : 'Start Live Listening';
  if (liveButton) liveButton.classList.toggle('tars-power-on', terminalVoiceMode === 'live');
  if (micOffButton) {
    micOffButton.textContent = terminalVoiceMode === 'off' ? 'MIC ON' : 'MIC OFF';
    micOffButton.classList.toggle('tars-power-off', terminalVoiceMode === 'off');
  }

  // Synchronize Toggle Switches
  if (switchLive) {
    switchLive.setAttribute('aria-checked', terminalVoiceMode === 'live' ? 'true' : 'false');
    switchLive.classList.toggle('disabled', backendUnavailable || terminalVoiceMode === 'starting');
    switchLive.setAttribute('aria-disabled', (backendUnavailable || terminalVoiceMode === 'starting') ? 'true' : 'false');
  }
  if (switchMic) {
    const isMicActive = terminalVoiceMode !== 'off' && !backendUnavailable;
    switchMic.setAttribute('aria-checked', isMicActive ? 'true' : 'false');
    switchMic.classList.toggle('disabled', backendUnavailable || terminalVoiceMode === 'starting');
    switchMic.setAttribute('aria-disabled', (backendUnavailable || terminalVoiceMode === 'starting') ? 'true' : 'false');
  }

  if (chatButton) chatButton.classList.toggle('btn-primary', terminalVoiceMode === 'live');
  if (chatButton) chatButton.classList.toggle('btn-outline', terminalVoiceMode !== 'live');
  if (chatMic) chatMic.classList.toggle('btn-primary', terminalVoiceMode === 'live');
  [liveButton, micOffButton, chatButton, chatMic].filter(Boolean).forEach(control => {
    control.disabled = backendUnavailable || terminalVoiceMode === 'starting';
  });
  if (window.browserVoiceSession) {
    window.browserVoiceSession.setMode(terminalVoiceMode);
  }
}
window.updateTerminalVoiceUI = updateTerminalVoiceUI;

function startLiveVoiceListen() {
  if (window.__isAssistantSpeaking) return;
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    if (typeof showSonner === 'function') {
      showSonner("Speech Recognition Unavailable", "Please use Safari or Chrome to use microphone speech recognition.");
    }
    return;
  }

  try {
    primeSafariAudioContext();
    userExplicitlyStopped = false;

    if (globalSpeechRec) {
      try { globalSpeechRec.stop(); } catch(e){}
    }

    globalSpeechRec = new SpeechRec();
    globalSpeechRec.continuous = false;
    globalSpeechRec.interimResults = true;
    globalSpeechRec.lang = 'en-US';

    const chatInp = document.getElementById('chat-input');
    const liveBtn = document.getElementById('btn-chat-live-listen');
    const liveDot = document.getElementById('live-listen-dot');
    const liveLabel = document.getElementById('live-listen-label');
    const micBtn = document.getElementById('btn-chat-mic');
    const topLiveBtn = document.getElementById('btn-topbar-live-listen');
    const topLiveDot = document.getElementById('topbar-live-dot');
    const topLiveText = document.getElementById('topbar-live-text');
    const orb = document.getElementById('live-ai-orb');
    const orbState = document.getElementById('live-orb-state-text');

    globalSpeechRec.onstart = () => {
      isLiveListenActive = true;
      if (liveBtn) {
        liveBtn.classList.add('btn-primary');
        liveBtn.classList.remove('btn-outline');
      }
      if (liveDot) liveDot.style.background = '#ef4444';
      if (liveLabel) liveLabel.textContent = '🎙️ Listening...';
      if (micBtn) micBtn.style.background = 'rgba(239, 68, 68, 0.25)';

      if (topLiveBtn) {
        topLiveBtn.style.background = 'rgba(239, 68, 68, 0.18)';
        topLiveBtn.style.borderColor = '#ef4444';
      }
      if (topLiveDot) topLiveDot.style.background = '#ef4444';
      if (topLiveText) {
        topLiveText.textContent = 'Listening...';
        topLiveText.style.color = '#ef4444';
      }

      if (orb) {
        orb.classList.remove('idle', 'speaking');
        orb.classList.add('listening');
      }
      if (orbState) orbState.textContent = 'Listening to your voice...';

      // Synchronize Card 3 Terminal Live Listen Switch / Button & Orb State
      const tarsListenBadge = document.getElementById('tars-live-listen-badge');
      const tarsLiveBtn = document.getElementById('btn-tars-live-listen');
      const switchLive = document.getElementById('switch-tars-live-listen');
      if (switchLive) switchLive.setAttribute('aria-checked', 'true');
      if (tarsListenBadge) {
        tarsListenBadge.textContent = 'STOP';
        tarsListenBadge.style.color = '#10b981';
      }
      if (tarsLiveBtn) {
        tarsLiveBtn.style.background = 'rgba(16, 185, 129, 0.12)';
        tarsLiveBtn.style.borderColor = '#10b981';
        tarsLiveBtn.style.color = '#10b981';
      }
      if (window.tarsController) {
        window.tarsController.setState('listening');
      }

      if (chatInp) chatInp.placeholder = 'Listening... Speak your request clearly.';
    };

    globalSpeechRec.onresult = (e) => {
      let interim = '';
      let finalTxt = '';
      for (let i = e.resultIndex; i < e.results.length; ++i) {
        if (e.results[i].isFinal) {
          finalTxt += e.results[i][0].transcript;
        } else {
          interim += e.results[i][0].transcript;
        }
      }
      if (chatInp) {
        chatInp.value = finalTxt || interim;
        autoResizeTextarea(chatInp);
      }
      const heardLine = document.getElementById('live-heard-text');
      if (heardLine && (finalTxt || interim)) {
        heardLine.textContent = `"${finalTxt || interim}"`;
      }
      if (finalTxt.trim()) {
        stopLiveVoiceListen(false);
        submitPrompt();
      }
    };

    globalSpeechRec.onerror = (e) => {
      console.warn("Speech recognition notice:", e.error);
      if (e.error !== 'no-speech') {
        isLiveListenActive = false;
      }
    };

    globalSpeechRec.onend = () => {
      isLiveListenActive = false;
      stopLiveVoiceListen(false);
    };

    if ('speechSynthesis' in window && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }
    globalSpeechRec.start();
  } catch (err) {
    console.error("Live listen start failed:", err);
    stopLiveVoiceListen(false);
  }
}

function stopLiveVoiceListen(explicitByUser = false) {
  if (explicitByUser) {
    userExplicitlyStopped = true;
  }
  isLiveListenActive = false;
  if (globalSpeechRec) {
    try { globalSpeechRec.stop(); } catch(e){}
    globalSpeechRec = null;
  }
  const liveBtn = document.getElementById('btn-chat-live-listen');
  const liveDot = document.getElementById('live-listen-dot');
  const liveLabel = document.getElementById('live-listen-label');
  const micBtn = document.getElementById('btn-chat-mic');
  const topLiveBtn = document.getElementById('btn-topbar-live-listen');
  const topLiveDot = document.getElementById('topbar-live-dot');
  const topLiveText = document.getElementById('topbar-live-text');
  const chatInp = document.getElementById('chat-input');
  const orb = document.getElementById('live-ai-orb');
  const orbState = document.getElementById('live-orb-state-text');

  if (liveBtn) {
    liveBtn.classList.remove('btn-primary');
    liveBtn.classList.add('btn-outline');
  }
  if (liveDot) liveDot.style.background = '#10b981';
  if (liveLabel) liveLabel.textContent = 'Live Listen';
  if (micBtn) micBtn.style.background = '';

  if (topLiveBtn) {
    topLiveBtn.style.background = 'rgba(20, 184, 166, 0.12)';
    topLiveBtn.style.borderColor = 'rgba(20, 184, 166, 0.35)';
  }
  if (topLiveDot) topLiveDot.style.background = '#10b981';
  if (topLiveText) {
    topLiveText.textContent = 'Live Listen';
    topLiveText.style.color = 'var(--lg-teal)';
  }

  if (orb && !orb.classList.contains('speaking')) {
    orb.classList.remove('listening');
    orb.classList.add('idle');
  }
  if (orbState && orbState.textContent.includes('Listening')) {
    orbState.textContent = 'Standby • Say "Hey" or click to speak';
  }

  // Synchronize Card 3 Terminal Live Listen Switch / Button & Orb State
  const tarsListenBadge = document.getElementById('tars-live-listen-badge');
  const tarsLiveBtn = document.getElementById('btn-tars-live-listen');
  const switchLive = document.getElementById('switch-tars-live-listen');
  if (switchLive) switchLive.setAttribute('aria-checked', 'false');
  if (tarsListenBadge) {
    tarsListenBadge.textContent = 'START';
    tarsListenBadge.style.color = '#38bdf8';
  }
  if (tarsLiveBtn) {
    tarsLiveBtn.style.background = 'rgba(255, 255, 255, 0.04)';
    tarsLiveBtn.style.borderColor = 'rgba(56, 189, 248, 0.28)';
    tarsLiveBtn.style.color = '#38bdf8';
  }
  if (window.tarsController && !window.__isAssistantSpeaking) {
    window.tarsController.setState('standby');
  }

  if (chatInp) chatInp.placeholder = 'Speak with Live Listen or type a message (Enter to send)...';
}

// --- Microphone Permission & Live Audio Meter Management ---
let _micAudioStream = null;
let _micAudioContext = null;
let _micAnalyser = null;
let _micMeterAnimFrame = null;

async function checkMicPermissionStatus() {
  const badge = document.getElementById('cfg-mic-perm-badge');
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    if (badge) {
      badge.textContent = 'Unsupported';
      badge.className = 'badge badge-outline';
    }
    return 'unsupported';
  }

  if (navigator.permissions && navigator.permissions.query) {
    try {
      const perm = await navigator.permissions.query({ name: 'microphone' });
      updateMicBadge(perm.state);
      perm.onchange = () => updateMicBadge(perm.state);
      return perm.state;
    } catch (e) {
      // Browser doesn't support query({ name: 'microphone' })
    }
  }
  return 'unknown';
}

function updateMicBadge(state) {
  const badge = document.getElementById('cfg-mic-perm-badge');
  if (!badge) return;
  if (state === 'granted') {
    badge.textContent = 'Ready / Allowed';
    badge.className = 'badge badge-success';
    badge.style.color = '#22c55e';
    badge.style.borderColor = '#22c55e';
  } else if (state === 'denied') {
    badge.textContent = 'Blocked / Denied';
    badge.className = 'badge badge-warning';
    badge.style.color = '#ef4444';
    badge.style.borderColor = '#ef4444';
  } else {
    badge.textContent = 'Prompt Needed';
    badge.className = 'badge badge-outline';
  }
}

async function requestMicPermission(interactive = false) {
  const btn = document.getElementById('btn-request-mic-perm');
  const btnText = document.getElementById('btn-request-mic-text');
  const statusTxt = document.getElementById('cfg-mic-test-status');
  const meterWrap = document.getElementById('cfg-mic-meter-wrap');
  const meterBar = document.getElementById('cfg-mic-meter-bar');

  if (btnText) btnText.textContent = 'Requesting...';
  if (statusTxt) statusTxt.textContent = 'Listening for audio levels...';

  try {
    if (_micAudioStream) {
      _micAudioStream.getTracks().forEach(t => t.stop());
      _micAudioStream = null;
    }
    if (_micMeterAnimFrame) {
      cancelAnimationFrame(_micMeterAnimFrame);
      _micMeterAnimFrame = null;
    }

    _micAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    updateMicBadge('granted');

    if (btnText) btnText.textContent = 'Testing Mic (Active)';
    if (statusTxt) statusTxt.textContent = 'Microphone active! Speak to see live level:';
    if (meterWrap) meterWrap.style.display = 'block';

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      _micAudioContext = new AudioContextClass();
      if (_micAudioContext.state === 'suspended') {
        await _micAudioContext.resume();
      }
      const source = _micAudioContext.createMediaStreamSource(_micAudioStream);
      _micAnalyser = _micAudioContext.createAnalyser();
      _micAnalyser.fftSize = 256;
      source.connect(_micAnalyser);

      const dataArray = new Uint8Array(_micAnalyser.frequencyBinCount);
      const updateMeter = () => {
        if (!_micAnalyser || !_micAudioStream) return;
        _micAnalyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        const pct = Math.min(100, Math.round((avg / 128) * 100));
        if (meterBar) meterBar.style.width = `${pct}%`;
        _micMeterAnimFrame = requestAnimationFrame(updateMeter);
      };
      updateMeter();

      setTimeout(() => {
        if (btnText) btnText.textContent = 'Test Microphone Access';
        if (statusTxt) statusTxt.textContent = 'Microphone test completed (Ready).';
      }, 12000);
    }

    if (interactive && typeof showSonner === 'function') {
      showSonner('Microphone Access Granted', 'Browser microphone is connected and ready for speech.');
    }
  } catch (err) {
    console.warn('Microphone permission request error:', err);
    updateMicBadge('denied');
    if (btnText) btnText.textContent = 'Request Permission';
    if (statusTxt) statusTxt.textContent = 'Access blocked. Click the browser lock/mic icon in the address bar to allow.';
    if (meterWrap) meterWrap.style.display = 'none';
    if (interactive && typeof showSonner === 'function') {
      showSonner('Microphone Blocked', 'Please grant microphone access in your browser address bar.');
    }
  }
}
async function requestTerminalMicPermission() {
  try {
    const res = await fetch('/api/system/request_mic_permission', { method: 'POST' });
    const data = await res.json();
    if (data.granted) {
      if (typeof showSonner === 'function') {
        showSonner('Terminal Mic Granted', data.message || 'Microphone access is active for Terminal.');
      }
    } else {
      if (typeof showSonner === 'function') {
        showSonner('macOS Settings Opened', data.message || 'Please toggle the switch ON for Terminal, then restart.');
      }
    }
  } catch (err) {
    if (typeof showSonner === 'function') {
      showSonner('Permission Check Failed', err.message);
    }
  }
}
window.requestTerminalMicPermission = requestTerminalMicPermission;
window.requestMicPermission = requestMicPermission;
window.checkMicPermissionStatus = checkMicPermissionStatus;

// Check / request permissions on app startup
setTimeout(() => {
  checkMicPermissionStatus();
}, 500);
