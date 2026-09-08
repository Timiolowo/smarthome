/* ==========================================================================
   LIVE DISPLAY CONTROLLER (Kiosk, Voice HUD & Telemetry Stream)
   ========================================================================== */
  let currentTelemetryFilter = 'all';
  let telemetryAutoScroll = true;
  let isKioskModeActive = false;
  let webSpeechRecognition = null;
  let isWebMicListening = false;

  // 1. Clock & Ambient Date
  function updateClock() {
    const clockEl = document.getElementById('kiosk-clock');
    const dateEl = document.getElementById('kiosk-date');
    const greetingEl = document.getElementById('kiosk-greeting-text');
    if (!clockEl) return;

    const now = new Date();
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = String(hours % 12 || 12).padStart(2, '0');

    clockEl.innerHTML = `${displayHours}:${minutes}:${seconds}<span class="time-ampm" id="kiosk-ampm">${ampm}</span>`;

    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (dateEl) {
      dateEl.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
        <span>${days[now.getDay()]}, ${months[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}</span>
      `;
    }

    if (greetingEl) {
      const user = cachedStatus?.config?.user_name || 'Timilehin';
      let salutation = 'Welcome home';
      if (hours < 12) salutation = 'Good morning';
      else if (hours < 17) salutation = 'Good afternoon';
      else salutation = 'Good evening';
      greetingEl.innerText = `${salutation}, ${user}`;
    }
  }

  // 2. Kiosk Mode Toggle (Ambient Fullscreen)
  function toggleKioskMode(enable) {
    isKioskModeActive = enable !== undefined ? enable : !isKioskModeActive;
    if (isKioskModeActive) {
      document.body.classList.add('kiosk-mode');
      showTab('tab-livedisplay', document.getElementById('nav-item-livedisplay'));
      try {
        if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
          document.documentElement.requestFullscreen().catch(() => {});
        }
      } catch (e) {}
      showToast("Ambient Kiosk Mode activated. Press ESC to exit.");
    } else {
      document.body.classList.remove('kiosk-mode');
      try {
        if (document.fullscreenElement && document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        }
      } catch (e) {}
    }
  }

  // Handle Fullscreen exit / ESC key
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && isKioskModeActive) {
      toggleKioskMode(false);
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isKioskModeActive) {
      toggleKioskMode(false);
    } else if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      toggleKioskMode();
    }
  });

  // 3. Poll Live Display Data & Active Timers
  async function pollLiveDisplay() {
    const liveTab = document.getElementById('tab-livedisplay');
    if (!liveTab || !liveTab.classList.contains('visible')) return;

    const startTime = performance.now();
    try {
      const res = await fetch('/api/status');
      const latencyMs = Math.round(performance.now() - startTime);
      const data = await res.json();
      cachedStatus = data;

      // Update ping latency
      const latEl = document.getElementById('telemetry-latency');
      if (latEl) latEl.innerText = `${latencyMs} ms`;

      // Presence Beacon & Info
      const isHome = data.state?.presence?.is_user_home;
      const userName = data.config?.user_name || 'Timilehin';
      const beaconEl = document.getElementById('live-beacon-indicator');
      const beaconStatus = document.getElementById('live-beacon-status');
      const presenceIp = document.getElementById('live-presence-ip');
      const kioskUser = document.getElementById('kiosk-user-presence');
      const kioskPresenceBadge = document.getElementById('kiosk-presence-badge');
      const kioskPresenceMeta = document.getElementById('kiosk-presence-meta');

      if (kioskUser) kioskUser.innerText = userName;
      if (presenceIp) presenceIp.innerText = `Target IP: ${data.config?.phone_ip || '192.168.1.150'}`;

      if (beaconEl && beaconStatus) {
        if (isHome) {
          beaconEl.className = 'live-beacon-pill';
          beaconStatus.innerText = `ONLINE • ${userName} is Home`;
          if (kioskPresenceBadge) {
            kioskPresenceBadge.className = 'badge badge-green';
            kioskPresenceBadge.innerText = 'Home';
          }
          if (kioskPresenceMeta) kioskPresenceMeta.innerText = 'Device connected on Wi-Fi • Standby';
        } else {
          beaconEl.className = 'live-beacon-pill away';
          beaconStatus.innerText = `AWAY • Monitoring Home Network`;
          if (kioskPresenceBadge) {
            kioskPresenceBadge.className = 'badge badge-gray';
            kioskPresenceBadge.innerText = 'Away';
          }
          if (kioskPresenceMeta) kioskPresenceMeta.innerText = 'Waiting for phone to appear on Wi-Fi';
        }
      }

      // Snapshot cards
      const powerVal = document.getElementById('kiosk-power-val');
      if (powerVal) {
        const pwr = data.state?.power;
        const grid = pwr?.grid_available ? 'Grid Active' : 'Inverter Battery';
        const batt = pwr?.inverter_battery_percentage ? ` (${pwr.inverter_battery_percentage}%)` : '';
        powerVal.innerText = `${grid}${batt}`;
      }

      // Active Timers Render
      const timersListEl = document.getElementById('live-timers-list');
      const timersCountEl = document.getElementById('live-timers-count');
      const timers = data.active_timers_list || [];
      if (timersCountEl) timersCountEl.innerText = `${timers.length} Running`;

      if (timersListEl) {
        if (timers.length === 0) {
          timersListEl.innerHTML = '<div class="timer-empty-state">No active alarms or timers running</div>';
        } else {
          timersListEl.innerHTML = timers.map(t => {
            const rem = Math.max(0, Math.round(t.remaining_seconds));
            const m = Math.floor(rem / 60);
            const s = String(rem % 60).padStart(2, '0');
            return `
              <div class="timer-ring-card">
                <div>
                  <div class="timer-ring-label">⏰ ${t.label || 'Alarm'}</div>
                  <div class="timer-ring-meta">${t.display_time} • ${t.progress_pct}% elapsed</div>
                </div>
                <div class="timer-countdown-val">${m}:${s}</div>
              </div>
            `;
          }).join('');
        }
      }

      // Voice Orb & Subtitles
      const asstRuntime = data.assistant_runtime || {};
      const orbEl = document.getElementById('live-ai-orb');
      const orbStateText = document.getElementById('live-orb-state-text');
      const heardEl = document.getElementById('live-heard-text');
      const replyEl = document.getElementById('live-reply-text');

      if (heardEl && asstRuntime.last_heard) {
        heardEl.innerText = `"${asstRuntime.last_heard}"`;
      }
      if (replyEl && asstRuntime.last_reply) {
        replyEl.innerText = `"${asstRuntime.last_reply}"`;
      }

      // Only update orb from server if web mic is not overriding
      if (!isWebMicListening && orbEl && orbStateText) {
        const rawState = (asstRuntime.state || 'IDLE').toUpperCase();
        orbEl.className = 'ai-orb-wrapper';

        if (rawState === 'LISTENING' || rawState === 'WAITING_FOR_GREETING') {
          orbEl.classList.add('listening');
          orbStateText.innerText = 'Listening for speech...';
        } else if (rawState === 'THINKING') {
          orbEl.classList.add('thinking');
          orbStateText.innerText = 'Processing thought & tools...';
        } else if (rawState === 'SPEAKING') {
          orbEl.classList.add('speaking');
          orbStateText.innerText = 'Speaking response aloud...';
        } else if (rawState === 'AWAY') {
          orbStateText.innerText = 'Waiting for arrival...';
        } else {
          orbStateText.innerText = `Standby • Say "Hey" or "Hello"`;
        }
      }

    } catch (e) {
      console.warn("pollLiveDisplay error:", e);
    }
  }

  // 4. Telemetry Stream & Log Events
  function setTelemetryFilter(category, btn) {
    currentTelemetryFilter = category;
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    if (btn) btn.classList.add('active');
    pollLiveEvents(true);
  }

  function toggleTelemetryAutoScroll() {
    telemetryAutoScroll = !telemetryAutoScroll;
    const btn = document.getElementById('btn-autoscroll');
    if (btn) btn.innerText = `Auto-scroll: ${telemetryAutoScroll ? 'ON' : 'OFF'}`;
  }

  async function pollLiveEvents(force = false) {
    const liveTab = document.getElementById('tab-livedisplay');
    if (!liveTab || (!liveTab.classList.contains('visible') && !force)) return;

    try {
      const url = `/api/events?limit=40&category=${encodeURIComponent(currentTelemetryFilter)}`;
      const res = await fetch(url);
      const data = await res.json();
      const events = data.events || [];

      const feedEl = document.getElementById('telemetry-feed');
      const countEl = document.getElementById('telemetry-count-label');
      if (countEl) countEl.innerText = `${events.length} events loaded`;

      if (feedEl) {
        if (events.length === 0) {
          feedEl.innerHTML = '<div style="color:var(--ink-3); text-align:center; padding:24px 0;">No events in this category yet.</div>';
        } else {
          feedEl.innerHTML = events.map(e => {
            const timeStr = e.timestamp ? e.timestamp.split('T')[1]?.split('.')[0] || e.timestamp : '';
            const cat = (e.category || 'system').toLowerCase();
            return `
              <div class="telemetry-row">
                <span class="telemetry-time">${timeStr}</span>
                <span class="telemetry-tag ${cat}">${cat}</span>
                <span class="telemetry-msg">${escapeHtml(e.note || '')}</span>
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

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  // 5. In-Browser Speech Recognition & Push-to-Talk
  function toggleWebSpeechMic() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      showToast("Speech recognition not supported in this browser. Use laptop microphone or type below.");
      return;
    }

    const micBtn = document.getElementById('btn-live-mic');
    const micText = document.getElementById('btn-live-mic-text');
    const orb = document.getElementById('live-ai-orb');
    const orbText = document.getElementById('live-orb-state-text');
    const heardEl = document.getElementById('live-heard-text');

    if (isWebMicListening && webSpeechRecognition) {
      webSpeechRecognition.stop();
      return;
    }

    try {
      webSpeechRecognition = new SpeechRecognition();
      webSpeechRecognition.lang = 'en-US';
      webSpeechRecognition.interimResults = true;
      webSpeechRecognition.continuous = false;

      webSpeechRecognition.onstart = () => {
        isWebMicListening = true;
        if (micBtn) micBtn.classList.add('active-listening');
        if (micText) micText.innerText = 'Listening to your voice...';
        if (orb) {
          orb.className = 'ai-orb-wrapper listening';
        }
        if (orbText) orbText.innerText = 'Listening to your voice...';
      };

      webSpeechRecognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        if (heardEl) heardEl.innerText = `"${transcript}"`;

        if (event.results[0].isFinal) {
          triggerQuickSpoken(transcript);
        }
      };

      webSpeechRecognition.onerror = (event) => {
        console.warn("Web speech error:", event.error);
        stopWebMic();
      };

      webSpeechRecognition.onend = () => {
        stopWebMic();
      };

      webSpeechRecognition.start();
    } catch (e) {
      console.error("Speech init error:", e);
      stopWebMic();
    }
  }

  function stopWebMic() {
    isWebMicListening = false;
    const micBtn = document.getElementById('btn-live-mic');
    const micText = document.getElementById('btn-live-mic-text');
    if (micBtn) micBtn.classList.remove('active-listening');
    if (micText) micText.innerText = 'Push to Talk (Browser Mic)';
  }

  // 6. Quick Spoken Prompts & Direct Execution
  async function triggerQuickSpoken(phrase) {
    if (!phrase || !phrase.trim()) return;
    const orb = document.getElementById('live-ai-orb');
    const orbText = document.getElementById('live-orb-state-text');
    const heardEl = document.getElementById('live-heard-text');
    const replyEl = document.getElementById('live-reply-text');

    if (heardEl) heardEl.innerText = `"${phrase}"`;
    if (orb) orb.className = 'ai-orb-wrapper thinking';
    if (orbText) orbText.innerText = 'Thinking & processing...';

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: phrase})
      });
      const data = await res.json();
      const reply = data.reply || 'Request completed.';

      if (replyEl) replyEl.innerText = `"${reply}"`;
      if (orb) orb.className = 'ai-orb-wrapper speaking';
      if (orbText) orbText.innerText = 'Assistant speaking...';

      // Optional: use browser SpeechSynthesis if supported for audio feedback
      if ('speechSynthesis' in window) {
        const utter = new SpeechSynthesisUtterance(reply);
        utter.rate = 1.05;
        utter.onend = () => {
          if (orb) orb.className = 'ai-orb-wrapper';
          if (orbText) orbText.innerText = 'Standby • Say "Hey" or "Hello"';
        };
        window.speechSynthesis.speak(utter);
      } else {
        setTimeout(() => {
          if (orb) orb.className = 'ai-orb-wrapper';
          if (orbText) orbText.innerText = 'Standby • Say "Hey" or "Hello"';
        }, 3000);
      }

      pollLiveEvents(true);
      loadStatus();
    } catch (e) {
      if (replyEl) replyEl.innerText = `Error: ${e.message}`;
      if (orb) orb.className = 'ai-orb-wrapper';
      if (orbText) orbText.innerText = 'Standby';
    }
  }

  // Start real-time live clock and polling intervals
  setInterval(updateClock, 1000);
  setInterval(pollLiveDisplay, 1500);
  setInterval(() => pollLiveEvents(false), 2000);
