/* ==========================================================================
   LIVE DISPLAY CONTROLLER — ZERO EMOJIS, 100% SVG
   Documented Component Systems:
   - Magic UI (Ripple Concentric Orb, Number Ticker)
   - Apple StandBy / Calm Smart-Home Interface
   ========================================================================== */
let currentTelemetryFilter = 'all';
let telemetryAutoScroll = true;
let isKioskModeActive = false;
let isTelemetryDrawerOpen = false;
let webSpeechRecognition = null;
let isWebMicListening = false;

const safeEscapeHtml = (str) => (typeof escapeHtml === 'function' ? escapeHtml(str) : String(str || '').replace(/[&<>'"]/g, tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag] || tag)));

// 1. Clock & Ambient Date
function updateClock() {
  const clockEl = document.getElementById('kiosk-clock');
  const ampmEl = document.getElementById('kiosk-ampm');
  const dateEl = document.getElementById('kiosk-date');
  const greetingEl = document.getElementById('kiosk-greeting-text');
  if (!clockEl) return;

  const now = new Date();
  let hours = now.getHours();
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const displayHours = String(hours % 12 || 12).padStart(2, '0');

  clockEl.textContent = `${displayHours}:${minutes}`;
  if (ampmEl) ampmEl.textContent = ampm;

  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  if (dateEl) {
    dateEl.textContent = `${days[now.getDay()]}, ${months[now.getMonth()]} ${now.getDate()}`;
  }

  if (greetingEl) {
    const user = (window.cachedStatus?.config?.user_name) || 'Timilehin';
    let salutation = 'Welcome home';
    if (hours < 12) salutation = 'Good morning';
    else if (hours < 17) salutation = 'Good afternoon';
    else salutation = 'Good evening';
    greetingEl.textContent = `${salutation}, ${user}`;
  }
}

// 2. Kiosk Mode Toggle (Ambient Fullscreen)
function toggleKioskMode(enable) {
  isKioskModeActive = enable !== undefined ? enable : !isKioskModeActive;
  const enterIcon = document.getElementById('icon-fullscreen-enter');
  const exitIcon = document.getElementById('icon-fullscreen-exit');
  const navBtn = document.getElementById('btn-tars-fullscreen-toggle');
  const stageBtn = document.getElementById('btn-tars-stage-fullscreen');

  if (isKioskModeActive) {
    document.body.classList.add('kiosk-mode');
    if (enterIcon) enterIcon.style.display = 'none';
    if (exitIcon) exitIcon.style.display = 'inline-block';
    if (navBtn) navBtn.classList.add('active');
    if (stageBtn) stageBtn.classList.add('active');

    const navItem = document.getElementById('nav-btn-livedisplay');
    if (typeof showTab === 'function') {
      showTab('tab-livedisplay', navItem);
    }
    try {
      if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {});
      }
    } catch (e) {}
    if (typeof showSonner === 'function') {
      showSonner("Fullscreen HUD activated", "Press ESC or click the button to exit.");
    }
  } else {
    document.body.classList.remove('kiosk-mode');
    if (enterIcon) enterIcon.style.display = 'inline-block';
    if (exitIcon) exitIcon.style.display = 'none';
    if (navBtn) navBtn.classList.remove('active');
    if (stageBtn) stageBtn.classList.remove('active');

    try {
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    } catch (e) {}
  }
}
window.toggleKioskMode = toggleKioskMode;

// 3. Telemetry Drawer & Modals
function toggleTelemetryDrawer(open) {
  isTelemetryDrawerOpen = open !== undefined ? open : !isTelemetryDrawerOpen;
  const drawer = document.getElementById('standby-telemetry-drawer');
  if (drawer) {
    if (isTelemetryDrawerOpen) {
      drawer.classList.add('open');
      pollLiveEvents(true);
    } else {
      drawer.classList.remove('open');
    }
  }
}
window.toggleTelemetryDrawer = toggleTelemetryDrawer;

function toggleAudioHealthModal(open) {
  const modal = document.getElementById('audio-settings-dialog');
  if (!modal) return;
  const show = open !== undefined ? open : !modal.classList.contains('open');
  if (show) {
    modal.classList.add('open');
  } else {
    modal.classList.remove('open');
  }
}
window.toggleAudioHealthModal = toggleAudioHealthModal;

// Handle Fullscreen exit / ESC key
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement && isKioskModeActive) {
    toggleKioskMode(false);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (isTelemetryDrawerOpen) {
      toggleTelemetryDrawer(false);
    } else if (isKioskModeActive) {
      toggleKioskMode(false);
    }
    toggleAudioHealthModal(false);
  } else if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    toggleKioskMode();
  }
});

// 4. Poll Live Display Data & Active Timers
async function pollLiveDisplay() {
  const liveTab = document.getElementById('tab-livedisplay');
  if (!liveTab || !liveTab.classList.contains('visible')) return;

  const startTime = performance.now();
  try {
    const res = await fetch('/api/status');
    const latencyMs = Math.round(performance.now() - startTime);
    const data = await res.json();
    window.cachedStatus = data;

    // Latency Ping
    const latEl = document.getElementById('telemetry-latency');
    if (latEl) latEl.textContent = `${latencyMs} ms`;

    // Presence
    const isHome = data.state?.presence?.is_user_home;
    const userName = data.config?.user_name || 'Timilehin';
    const beaconEl = document.getElementById('live-beacon-indicator');
    const beaconStatus = document.getElementById('live-beacon-status');
    const presenceIp = document.getElementById('live-presence-ip');

    if (presenceIp) {
      presenceIp.textContent = data.config?.phone_ip || '192.168.1.150';
    }

    if (beaconEl && beaconStatus) {
      if (isHome) {
        beaconEl.className = 'standby-presence-pill';
        beaconStatus.textContent = `${userName} is Home`;
      } else {
        beaconEl.className = 'standby-presence-pill away';
        beaconStatus.textContent = `Monitoring Home Network`;
      }
    }

    // Active Timers: Progressive Disclosure (Zero emojis: Lucide Clock SVG)
    const timersWrap = document.getElementById('standby-timers-container');
    const timersListEl = document.getElementById('live-timers-list');
    const timers = data.active_timers_list || [];

    if (timersWrap && timersListEl) {
      if (timers.length === 0) {
        timersWrap.style.display = 'none';
        timersListEl.innerHTML = '';
      } else {
        timersWrap.style.display = 'block';
        timersListEl.innerHTML = timers.map(t => {
          const rem = Math.max(0, Math.round(t.remaining_seconds));
          const m = Math.floor(rem / 60);
          const s = String(rem % 60).padStart(2, '0');
          return `
            <div class="standby-timer-pill">
              <span class="standby-timer-title">
                <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                ${safeEscapeHtml(t.label || 'Timer')}
              </span>
              <span class="standby-timer-val">${m}:${s}</span>
            </div>
          `;
        }).join('');
      }
    }

    // Audio Health helper if present
    if (typeof updateAudioHealth === 'function') {
      updateAudioHealth(data.voice_audio);
    }

    // Sync system power UI from polled status
    if (data.system_power) {
      const polledPower = data.system_power.powered_on;
      if (polledPower !== _systemPoweredOn) {
        updatePowerUI(polledPower);
      }
      if (typeof updateTerminalVoiceUI === 'function') {
        updateTerminalVoiceUI(data.system_power.voice_mode || 'wake');
      }
    }

    // AI Voice Orb & Floating Dialogue (Magic UI Ripple Visualizer)
    const asstRuntime = data.assistant_runtime || {};
    const orbEl = document.getElementById('live-ai-orb');
    const orbStateText = document.getElementById('live-orb-state-text');
    const heardEl = document.getElementById('live-heard-text');
    const replyEl = document.getElementById('live-reply-text');

    if (heardEl && asstRuntime.last_heard) {
      heardEl.textContent = `"${asstRuntime.last_heard}"`;
    }
    if (replyEl && asstRuntime.last_reply) {
      replyEl.textContent = `"${asstRuntime.last_reply}"`;
    }

    // Sync Orb animation states
    if (!isWebMicListening && orbEl && orbStateText) {
      const sttState = data.stt_status?.state;
      const rawState = (data.voice_audio?.state === 'OFFLINE' ? asstRuntime.state : data.voice_audio?.state || asstRuntime.state || 'IDLE').toUpperCase();

      if (sttState === 'LOADING' || rawState === 'LOADING_SPEECH_MODEL') {
        orbEl.className = 'magic-ripple-container thinking';
        orbStateText.innerHTML = `<span class="spinner-inline"></span> Initializing speech engine (Faster-Whisper)...`;
      } else if (['LISTENING', 'HEARING', 'WAITING_FOR_GREETING'].includes(rawState)) {
        orbEl.className = 'magic-ripple-container listening';
        orbStateText.innerHTML = `<span class="telemetry-eq-bars"><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span></span> Listening for speech...`;
      } else if (['THINKING', 'TRANSCRIBING', 'SYNTHESIZING', 'CALIBRATING'].includes(rawState)) {
        orbEl.className = 'magic-ripple-container thinking';
        orbStateText.textContent = data.voice_audio?.message || (rawState === 'TRANSCRIBING' ? 'Transcribing speech...' : 'Thinking about response...');
      } else if (rawState === 'SPEAKING') {
        orbEl.className = 'magic-ripple-container speaking';
        orbStateText.innerHTML = `<span class="telemetry-eq-bars"><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span></span> Speaking response...`;
      } else if (rawState === 'ERROR' || rawState === 'OFFLINE') {
        orbEl.className = 'magic-ripple-container idle';
        orbStateText.textContent = data.voice_audio?.message || 'Standby';
      } else if (rawState === 'AWAY') {
        orbEl.className = 'magic-ripple-container idle';
        orbStateText.textContent = 'Away • Monitoring';
      } else {
        orbEl.className = 'magic-ripple-container idle';
        const asstName = data.assistant?.name || 'Nova';
        orbStateText.textContent = `Standby • Say "${asstName}"`;
      }
    }

    // Synchronize UI visual engine, active tab, theme, and kiosk mode
    const ui = data.ui || data.state?.ui;
    if (ui) {
      if (ui.visual_engine && window.tarsController) {
        if (ui.visual_engine === '3d' && !window.tarsController.is3DMode) {
          window.tarsController.set3DMode(true);
        } else if (ui.visual_engine === '2d' && window.tarsController.is3DMode) {
          window.tarsController.set3DMode(false);
        }
      }
      if (ui.theme) {
        document.documentElement.setAttribute('data-theme', ui.theme);
      }
      if (ui.active_tab && ui.tab_updated_at && typeof window.showTab === 'function') {
        if (!window.__lastServerTabUpdatedAt) {
          window.__lastServerTabUpdatedAt = ui.tab_updated_at;
        } else if (ui.tab_updated_at > window.__lastServerTabUpdatedAt) {
          window.__lastServerTabUpdatedAt = ui.tab_updated_at;
          if (window.__currentTabId !== ui.active_tab) {
            const navItem = document.querySelector(`.tars-top-nav-btn[onclick*="${ui.active_tab}"], .sidebar-menu-btn[onclick*="${ui.active_tab}"]`);
            window.showTab(ui.active_tab, navItem, false, false);
          }
        }
      }
      if (ui.kiosk_mode !== undefined && typeof toggleKioskMode === 'function') {
        if (ui.kiosk_mode && !isKioskModeActive) toggleKioskMode(true);
        else if (!ui.kiosk_mode && isKioskModeActive) toggleKioskMode(false);
      }
    }

    // Check for active scheduled sleep / return countdown
    const activeSleep = data.active_sleep || data.downtime?.active_sleep || data.state?.downtime?.active_sleep;
    const sleepCountdownEl = document.getElementById('tars-sleep-countdown');
    const countdownValEl = document.getElementById('tars-countdown-val');
    const countdownSubEl = document.getElementById('tars-countdown-sub');

    let isSleeping = false;
    if (activeSleep) {
      let targetMs = 0;
      if (activeSleep.target_wake_timestamp) {
        targetMs = activeSleep.target_wake_timestamp * 1000;
      } else if (activeSleep.target_wake) {
        targetMs = typeof activeSleep.target_wake === 'number' ? activeSleep.target_wake * 1000 : new Date(activeSleep.target_wake).getTime();
      }

      const nowMs = Date.now();
      const remainingSec = Math.max(0, Math.floor((targetMs - nowMs) / 1000));

      if (remainingSec > 0) {
        isSleeping = true;
        if (sleepCountdownEl) sleepCountdownEl.style.display = 'flex';
        const mins = Math.floor(remainingSec / 60);
        const secs = remainingSec % 60;
        const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        if (countdownValEl) countdownValEl.textContent = timeStr;
        if (countdownSubEl) {
          const desc = activeSleep.duration_desc ? activeSleep.duration_desc.toUpperCase() : `${mins} MINS`;
          countdownSubEl.textContent = `COMING BACK ONLINE IN ${desc}`;
        }
      } else {
        if (sleepCountdownEl) sleepCountdownEl.style.display = 'none';
      }
    } else {
      if (sleepCountdownEl) sleepCountdownEl.style.display = 'none';
    }

    // Update Central Status / Voice Mode Label with dynamic name, error display, and active speech/capture priority
    const statusLabel = document.getElementById('terminal-voice-mode');
    const asstName = (data.assistant?.name || data.config?.assistant_name || 'Nova').toUpperCase();
    const isError = (data.voice_audio?.state === 'ERROR' || asstRuntime.state === 'ERROR' || (data.voice_audio?.message && data.voice_audio.message.toLowerCase().includes('blocked by macos')));

    // Check client-side active voice and speech states
    const isAssistantSpeaking = Boolean(window.__isAssistantSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking));
    const isTranscribing = Boolean(window.browserVoiceSession && window.browserVoiceSession.processing);
    const isUserSpeaking = Boolean(window.browserVoiceSession && window.browserVoiceSession.capturing);

    let activeState = 'standby';
    let activeLabelText = '';

    if (isError) {
      activeState = 'error';
      activeLabelText = data.voice_audio?.message || 'MICROPHONE BLOCKED / ERROR';
    } else if (isSleeping) {
      activeState = 'sleep';
      activeLabelText = 'STANDBY · SLEEP MODE';
    } else if (data.system_power?.powered_on === false) {
      activeState = 'standby';
      activeLabelText = 'SYSTEM OFFLINE · CLICK OR POWER ON';
    } else if (isAssistantSpeaking) {
      activeState = 'speaking';
      activeLabelText = 'SPEAKING RESPONSE...';
    } else if (isTranscribing) {
      activeState = 'thinking';
      activeLabelText = 'TRANSCRIBING & THINKING...';
    } else if (isUserSpeaking) {
      activeState = 'listening';
      activeLabelText = 'HEARING YOU...';
    } else {
      const runtimeState = (data.voice_audio?.state || asstRuntime.state || '').toUpperCase();
      const vMode = data.system_power?.voice_mode || 'wake';

      if (runtimeState === 'SPEAKING') {
        activeState = 'speaking';
        activeLabelText = 'SPEAKING RESPONSE...';
      } else if (['THINKING', 'TRANSCRIBING', 'SYNTHESIZING', 'CALIBRATING'].includes(runtimeState)) {
        activeState = 'thinking';
        activeLabelText = 'TRANSCRIBING & THINKING...';
      } else if (['LISTENING', 'HEARING'].includes(runtimeState)) {
        activeState = 'listening';
        activeLabelText = 'HEARING YOU...';
      } else if (vMode === 'off') {
        activeState = 'standby';
        activeLabelText = 'MICROPHONE OFF';
      } else if (vMode === 'live') {
        activeState = 'listening';
        activeLabelText = 'LIVE LISTENING';
      } else {
        activeState = 'standby';
        activeLabelText = `WAITING FOR “${asstName}”`;
      }
    }

    if (statusLabel) {
      if (isError) {
        statusLabel.classList.add('error');
      } else {
        statusLabel.classList.remove('error');
      }
      statusLabel.textContent = activeLabelText;
    }

    if (window.tarsController) {
      window.tarsController.setState(activeState);
    }

  } catch (e) {
    console.warn("pollLiveDisplay error:", e);
    if (typeof updateTerminalVoiceUI === 'function') {
      updateTerminalVoiceUI('offline');
    }
  }
}

// 5. Telemetry Stream & Log Events
function setTelemetryFilter(category, btn) {
  currentTelemetryFilter = category;
  document.querySelectorAll('.drawer-actions .btn').forEach(c => c.classList.remove('btn-primary'));
  if (btn) btn.classList.add('btn-primary');
  pollLiveEvents(true);
}
window.setTelemetryFilter = setTelemetryFilter;

function toggleTelemetryAutoScroll() {
  telemetryAutoScroll = !telemetryAutoScroll;
  const btn = document.getElementById('btn-autoscroll');
  if (btn) btn.textContent = `Auto-scroll: ${telemetryAutoScroll ? 'ON' : 'OFF'}`;
}
window.toggleTelemetryAutoScroll = toggleTelemetryAutoScroll;

async function pollLiveEvents(force = false) {
  const liveTab = document.getElementById('tab-livedisplay');
  if (!liveTab || (!liveTab.classList.contains('visible') && !force)) return;
  if (!isTelemetryDrawerOpen && !force) return;

  try {
    const url = `/api/events?limit=40&category=${encodeURIComponent(currentTelemetryFilter)}`;
    const res = await fetch(url);
    const data = await res.json();
    const events = data.events || [];

    const feedEl = document.getElementById('telemetry-feed');
    const countEl = document.getElementById('telemetry-count-label');
    if (countEl) countEl.textContent = `${events.length} events logged`;

    if (feedEl) {
      if (events.length === 0) {
        feedEl.innerHTML = '<div style="color:hsl(var(--muted-foreground)); text-align:center; padding:1.5rem 0;">No events in this category yet.</div>';
      } else {
        feedEl.innerHTML = events.map(e => {
          const timeStr = e.timestamp ? e.timestamp.split('T')[1]?.split('.')[0] || e.timestamp : '';
          const cat = (e.category || 'system').toLowerCase();
          return `
            <div class="drawer-log-line">
              <span class="drawer-log-time">${timeStr}</span>
              <span class="badge badge-outline" style="font-size:0.65rem; padding:0.1rem 0.35rem;">${cat}</span>
              <span style="color:hsl(var(--foreground));">${safeEscapeHtml(e.note || '')}</span>
            </div>
          `;
        }).join('');

        if (telemetryAutoScroll) {
          feedEl.scrollTop = feedEl.scrollHeight;
        }
      }
    }
  } catch (e) {
    console.warn("pollLiveEvents error:", e);
  }
}

// 6. Push-to-Talk Web Speech Mic
function toggleWebSpeechMic() {
  if (isWebMicListening) {
    stopWebMic();
  } else {
    startWebMic();
  }
}
window.toggleWebSpeechMic = toggleWebSpeechMic;

function startWebMic() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    if (typeof showSonner === 'function') {
      showSonner("Microphone unavailable", "Browser SpeechRecognition not supported in this browser.");
    }
    return;
  }

  try {
    webSpeechRecognition = new SpeechRecognition();
    webSpeechRecognition.continuous = false;
    webSpeechRecognition.interimResults = true;
    webSpeechRecognition.lang = 'en-US';

    const orb = document.getElementById('live-ai-orb');
    const orbText = document.getElementById('live-orb-state-text');
    const btn = document.getElementById('btn-live-mic');
    const btnText = document.getElementById('btn-live-mic-text');
    const heardEl = document.getElementById('live-heard-text');

    webSpeechRecognition.onstart = () => {
      isWebMicListening = true;
      if (orb) orb.className = 'magic-ripple-container listening';
      if (orbText) orbText.textContent = 'Listening via browser mic...';
      if (btn) btn.classList.add('recording');
      if (btnText) btnText.textContent = 'Listening...';
      if (heardEl) heardEl.textContent = 'Listening...';
    };

    webSpeechRecognition.onresult = (event) => {
      let interim = '';
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      if (heardEl) {
        heardEl.textContent = `"${finalTranscript || interim}"`;
      }
      if (finalTranscript.trim()) {
        processVoiceInput(finalTranscript.trim());
      }
    };

    webSpeechRecognition.onerror = (event) => {
      console.warn("Web speech error:", event.error);
      stopWebMic();
    };

    webSpeechRecognition.onend = () => {
      stopWebMic();
    };

    window.speechSynthesis?.cancel();
    webSpeechRecognition.start();
  } catch (e) {
    console.error("Speech init error:", e);
    stopWebMic();
  }
}

function stopWebMic() {
  isWebMicListening = false;
  if (webSpeechRecognition) {
    try { webSpeechRecognition.stop(); } catch(e){}
    webSpeechRecognition = null;
  }
  const btn = document.getElementById('btn-live-mic');
  const btnText = document.getElementById('btn-live-mic-text');
  if (btn) btn.classList.remove('recording');
  if (btnText) btnText.textContent = 'Voice Mic';
}

async function processVoiceInput(text) {
  const orb = document.getElementById('live-ai-orb');
  const orbText = document.getElementById('live-orb-state-text');
  const replyEl = document.getElementById('live-reply-text');

  if (orb) orb.className = 'magic-ripple-container thinking';
  if (orbText) orbText.textContent = 'Thinking...';

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Unable to send message');
    const reply = data.reply || 'Acknowledged.';

    if (replyEl) replyEl.textContent = `"${reply}"`;
    if (orb) orb.className = 'magic-ripple-container speaking';
    if (orbText) orbText.textContent = 'Speaking response...';

    // Speak aloud with Web Speech Synthesis if available
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(reply);
      const voice = typeof getBestNaturalVoice === 'function' ? getBestNaturalVoice() : null;
      if (voice) { utterance.voice = voice; utterance.lang = voice.lang; }
        if (orb) orb.className = 'magic-ripple-container idle';
        if (orbText) orbText.textContent = 'Standby • Say "Hey" or "Hello"';
        if (/standby mode|sleeping display|ambient standby/i.test(reply)) {
          if (typeof window.showIosStandby === 'function') window.showIosStandby();
        }
      };
      utterance.onerror = () => {
        if (orb) orb.className = 'magic-ripple-container idle';
        if (orbText) orbText.textContent = 'Standby • Say "Hey" or "Hello"';
      };
      window.speechSynthesis.speak(utterance);
    } else {
      setTimeout(() => {
        if (orb) orb.className = 'magic-ripple-container idle';
        if (orbText) orbText.textContent = 'Standby • Say "Hey" or "Hello"';
        if (/standby mode|sleeping display|ambient standby/i.test(reply)) {
          if (typeof window.showIosStandby === 'function') window.showIosStandby();
        }
      }, 3500);
    }
  } catch (err) {
    if (replyEl) replyEl.textContent = `"(Error: ${err.message})"`;
    if (orb) orb.className = 'magic-ripple-container idle';
  }
}

// --- System Power Toggle ---
let _systemPoweredOn = true;

async function toggleSystemPower() {
  const btn = document.getElementById('tars-power-toggle');
  const txt = document.getElementById('tars-power-text');
  if (btn) btn.disabled = true;
  try {
    const res = await fetch('/api/system/power', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'toggle'})
    });
    const data = await res.json();
    _systemPoweredOn = data.powered_on;
    updatePowerUI(data.powered_on);
  } catch (e) {
    console.error('Power toggle failed:', e);
  } finally {
    if (btn) btn.disabled = false;
  }
}
window.toggleSystemPower = toggleSystemPower;

function updatePowerUI(poweredOn) {
  const btn = document.getElementById('tars-power-toggle');
  const txt = document.getElementById('tars-power-text');
  const badge = document.querySelector('.tars-bottom-card .badge');
  const orb = document.querySelector('.magic-ripple-container');
  const orbText = document.getElementById('live-orb-state-text');

  if (txt) txt.textContent = poweredOn ? 'ONLINE' : 'OFFLINE';
  if (btn) {
    btn.classList.toggle('tars-power-on', poweredOn);
    btn.classList.toggle('tars-power-off', !poweredOn);
  }
  if (badge) {
    badge.textContent = poweredOn ? 'ONLINE' : 'OFFLINE';
    badge.style.color = poweredOn ? 'var(--accent, #38bdf8)' : '#ef4444';
    badge.style.borderColor = poweredOn ? 'var(--accent, #38bdf8)' : '#ef4444';
  }
  if (!poweredOn && orb) {
    orb.className = 'magic-ripple-container idle';
    if (orbText) orbText.textContent = 'System Powered Off';
  }
  _systemPoweredOn = poweredOn;
}

// --- "Hey Nova" Wake Word Standby ---
let _wakeRecognition = null;

function startWakeWordListener() {
  if (_wakeRecognition) return; // already listening
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  _wakeRecognition = new SpeechRecognition();
  _wakeRecognition.continuous = true;
  _wakeRecognition.interimResults = false;
  _wakeRecognition.lang = 'en-US';

  _wakeRecognition.onresult = (event) => {
    const asstName = (window.cachedStatus?.assistant?.name || window.cachedStatus?.config?.assistant_name || 'Nova').toLowerCase();
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (!event.results[i].isFinal) continue;
      const transcript = event.results[i][0].transcript.toLowerCase().trim();
      if (transcript.includes(`hey ${asstName}`) || transcript.includes(asstName) || transcript.includes('hey nova') || transcript.includes('nova')) {
        console.log('[Wake] Heard wake phrase:', transcript);
        stopWakeWordListener();
        // Auto power on
        fetch('/api/system/power', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({action: 'on'})
        }).then(r => r.json()).then(data => {
          updatePowerUI(data.powered_on);
          if (typeof showSonner === 'function') {
            showSonner('Wake Word', `${asstName.charAt(0).toUpperCase() + asstName.slice(1)} activated by voice!`);
          }
        }).catch(() => {});
        break;
      }
    }
  };

  _wakeRecognition.onerror = (event) => {
    if (event.error !== 'no-speech') {
      console.warn('[Wake] Recognition error:', event.error);
    }
  };

  _wakeRecognition.onend = () => {
    // Restart if still powered off
    if (!_systemPoweredOn && _wakeRecognition) {
      try { _wakeRecognition.start(); } catch(e) {}
    }
  };

  try { _wakeRecognition.start(); } catch(e) {}
}

function stopWakeWordListener() {
  if (_wakeRecognition) {
    try { _wakeRecognition.abort(); } catch(e) {}
    _wakeRecognition = null;
  }
}

// --- Collapsible Side Telemetry Column ---
function toggleTarsSideColumn(force) {
  const layout = document.querySelector('.tars-hub-layout');
  const sideCol = document.getElementById('tars-side-column') || document.querySelector('.tars-side-column');
  const btn = document.getElementById('btn-toggle-tars-side');
  if (!layout) return;

  const isCollapsed = force !== undefined ? force : !layout.classList.contains('side-collapsed');
  if (isCollapsed) {
    layout.classList.add('side-collapsed');
    if (sideCol) {
      sideCol.classList.add('collapsed');
      sideCol.style.setProperty('display', 'none', 'important');
    }
    if (btn) btn.classList.add('active');
    localStorage.setItem('tars_side_collapsed', 'true');
  } else {
    layout.classList.remove('side-collapsed');
    if (sideCol) {
      sideCol.classList.remove('collapsed');
      sideCol.style.removeProperty('display');
    }
    if (btn) btn.classList.remove('active');
    localStorage.setItem('tars_side_collapsed', 'false');
  }

  // Trigger resize events so 3D/2D particle canvases adjust smoothly during animation
  setTimeout(() => window.dispatchEvent(new Event('resize')), 160);
  setTimeout(() => window.dispatchEvent(new Event('resize')), 340);
}
window.toggleTarsSideColumn = toggleTarsSideColumn;

// Restore side column preference on startup & DOMContentLoaded
function restoreTarsSideColumn() {
  const isSavedCollapsed = localStorage.getItem('tars_side_collapsed') === 'true';
  if (isSavedCollapsed) {
    const layout = document.querySelector('.tars-hub-layout');
    const sideCol = document.getElementById('tars-side-column') || document.querySelector('.tars-side-column');
    const btn = document.getElementById('btn-toggle-tars-side');
    if (layout) layout.classList.add('side-collapsed');
    if (sideCol) {
      sideCol.classList.add('collapsed');
      sideCol.style.setProperty('display', 'none', 'important');
    }
    if (btn) btn.classList.add('active');
  }
}

restoreTarsSideColumn();
document.addEventListener('DOMContentLoaded', () => {
  restoreTarsSideColumn();
  const btn = document.getElementById('btn-toggle-tars-side');
  if (btn) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleTarsSideColumn();
    });
  }
});

// --- Cancel Active Sleep & Wake Assistant ---
async function cancelAssistantSleep() {
  try {
    const res = await fetch('/api/system/power', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'on'})
    });
    const data = await res.json();
    if (data.ok) {
      const countdownEl = document.getElementById('tars-sleep-countdown');
      if (countdownEl) countdownEl.style.display = 'none';
      if (typeof showSonner === 'function') {
        showSonner("Assistant Awakened", "Voice and reasoning core are back online.");
      }
      if (typeof pollLiveDisplay === 'function') pollLiveDisplay();
    }
  } catch (err) {
    console.warn("Failed to wake assistant:", err);
  }
}
window.cancelAssistantSleep = cancelAssistantSleep;

// Start timers and polling intervals
setInterval(updateClock, 1000);
setInterval(pollLiveDisplay, 500);
setInterval(() => pollLiveEvents(false), 2000);
