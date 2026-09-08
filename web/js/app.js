if (window.location.protocol === 'file:') {
    console.warn("SmartHome Assistant: Opened via file:// protocol. API calls require http://localhost:5050");
  }
  let cachedStatus = null;

  function setTheme(mode) {
    if (mode === 'light') {
      document.documentElement.classList.remove('dark');
      document.getElementById('btn-light').classList.add('active');
      document.getElementById('btn-dark').classList.remove('active');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.classList.add('dark');
      document.getElementById('btn-dark').classList.add('active');
      document.getElementById('btn-light').classList.remove('active');
      localStorage.setItem('theme', 'dark');
    }
  }

  // Load saved theme
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') {
    setTheme('light');
  }

  function showToast(msg) {
    const t = document.getElementById('toast');
    t.innerText = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2400);
  }

  function showTab(tabId, el) {
    document.querySelectorAll('.section-card').forEach(s => s.classList.remove('visible'));
    document.getElementById(tabId).classList.add('visible');

    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    if (el) el.classList.add('active');

    const titles = {
      'tab-livedisplay': ['Live Smart Display & Voice HUD', 'Ambient kiosk mode, real-time speech visualizer, and live telemetry stream.'],
      'tab-overview': ['Assistant Overview', 'Status, models, and real-time smart home controls.'],
      'tab-user-profile': ['What Nova Knows (About You)', 'Personal habits, entertainment tastes, power rules, and long-term memory.'],
      'tab-about-ai': ['About Nova (AI Assistant Dossier)', 'Identity, behavioral ground rules, privacy guarantees, and local architecture.'],
      'tab-alarms': ['Alarms & Timers', 'Live countdowns, cancel controls, and digital sound chime scheduler.'],
      'tab-config': ['Assistant Configuration', 'Change preferred name, assistant personality, and arrival options.'],
      'tab-chat': ['Chat Console', 'Direct text interaction with your agentic tools and brain.']
    };

    if (titles[tabId]) {
      document.getElementById('page-heading').innerText = titles[tabId][0];
      document.getElementById('page-subheading').innerText = titles[tabId][1];
    }

    if (tabId === 'tab-livedisplay') {
      updateClock();
      pollLiveDisplay();
      pollLiveEvents(true);
    }
  }

  let activeTimersCache = [];

  function formatTimeRemaining(totalSec) {
    if (totalSec <= 0) return '0s remaining';
    const hrs = Math.floor(totalSec / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = Math.floor(totalSec % 60);
    if (hrs > 0) return `${hrs}h ${mins}m ${secs}s left`;
    if (mins > 0) return `${mins}m ${secs.toString().padStart(2, '0')}s left`;
    return `${secs}s left`;
  }

  function renderActiveTimers(timers) {
    activeTimersCache = timers || [];
    const container = document.getElementById('alarms-active-timers-container');
    const pill = document.getElementById('active-timers-count-pill');
    const cancelAllBtn = document.getElementById('cancel-all-timers-btn');
    const sidebarBadge = document.getElementById('sidebar-timer-badge');
    const overviewTimersBadge = document.getElementById('disp-timers');

    const count = activeTimersCache.length;
    if (pill) pill.innerText = `${count} Running`;
    if (cancelAllBtn) cancelAllBtn.style.display = count > 1 ? 'inline-flex' : 'none';
    if (overviewTimersBadge) overviewTimersBadge.innerText = count;

    if (sidebarBadge) {
      sidebarBadge.innerText = count;
      sidebarBadge.style.display = count > 0 ? 'inline-block' : 'none';
    }

    if (!container) return;

    if (count === 0) {
      container.innerHTML = `<div class="empty-state-box">No active alarms or timers running right now.</div>`;
      return;
    }

    container.innerHTML = activeTimersCache.map(t => {
      const remText = formatTimeRemaining(t.remaining_seconds);
      const pct = Math.max(0, Math.min(100, t.progress_pct || 0));
      return `
        <div class="timer-item-card" id="timer-card-${t.id}">
          <div class="timer-item-header">
            <div class="timer-title-group">
              <div class="timer-pulsing-icon">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="13" r="8"></circle><path d="M12 9v4l2 2"></path></svg>
              </div>
              <div>
                <div style="font-weight:600; font-size:13.5px; color:var(--ink);">${(t.label || 'Alarm').toUpperCase()} &bull; ${t.display_time}</div>
                <div style="font-size:11.5px; color:var(--ink-3);">Target: ${t.target_display || 'Scheduled'}</div>
              </div>
            </div>
            <div style="display:flex; align-items:center; gap:10px;">
              <span class="timer-countdown-pill" id="timer-rem-${t.id}">
                <span class="pulse-dot" style="background:#f59e0b; width:6px; height:6px;"></span>
                ${remText}
              </span>
              <button class="btn btn-danger" style="padding:4px 10px; font-size:11.5px;" onclick="cancelTimer('${t.id}')">Cancel</button>
            </div>
          </div>
          <div class="timer-progress-wrap">
            <div class="timer-progress-bar" id="timer-bar-${t.id}" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  function tickActiveTimers() {
    if (!activeTimersCache || activeTimersCache.length === 0) return;
    let anyExpired = false;

    activeTimersCache.forEach(t => {
      t.remaining_seconds = Math.max(0, t.remaining_seconds - 1);
      const remEl = document.getElementById(`timer-rem-${t.id}`);
      const barEl = document.getElementById(`timer-bar-${t.id}`);

      if (remEl) {
        remEl.innerHTML = `<span class="pulse-dot" style="background:#f59e0b; width:6px; height:6px;"></span> ${formatTimeRemaining(t.remaining_seconds)}`;
      }

      if (barEl && t.total_seconds > 0) {
        const pct = Math.max(0, Math.min(100, Math.round((1 - (t.remaining_seconds / t.total_seconds)) * 100)));
        barEl.style.width = `${pct}%`;
      }

      if (t.remaining_seconds <= 0) {
        anyExpired = true;
      }
    });

    if (anyExpired) {
      loadStatus();
    }
  }

  setInterval(tickActiveTimers, 1000);

  async function cancelTimer(timerId) {
    try {
      const res = await fetch('/api/timer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'cancel', id: timerId})
      });
      const data = await res.json();
      showToast(data.message || 'Timer canceled');
      loadStatus();
    } catch (e) {
      showToast('Failed to cancel timer');
    }
  }

  async function cancelAllTimers() {
    if (!confirm('Cancel all active timers?')) return;
    try {
      const res = await fetch('/api/timer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'cancel_all'})
      });
      const data = await res.json();
      showToast(data.message || 'All timers canceled');
      loadStatus();
    } catch (e) {
      showToast('Failed to cancel timers');
    }
  }

  function renderUserProfile(mem) {
    if (!mem) return;
    const profile = mem.profile || {};
    const prefs = mem.preferences || {};
    const visitors = mem.household_members_and_visitors || [];

    const nameEl = document.getElementById('prof-user-name');
    if (nameEl) nameEl.innerText = profile.preferred_name || 'Timilehin';

    const locEl = document.getElementById('prof-location');
    if (locEl) locEl.innerText = profile.location || 'Nigeria';

    const tzEl = document.getElementById('prof-timezone');
    if (tzEl) tzEl.innerText = profile.timezone || 'Africa/Lagos';

    const roleEl = document.getElementById('prof-user-role');
    if (roleEl && visitors.length > 0) {
      roleEl.innerText = visitors[0].role || 'Owner / Primary Resident';
    }

    // Series chips
    const series = (prefs.entertainment && prefs.entertainment.favorite_series) ? prefs.entertainment.favorite_series : [];
    const seriesEl = document.getElementById('prof-series-chips');
    if (seriesEl && series.length > 0) {
      seriesEl.innerHTML = series.map(s => `<span class="tag-chip">🎬 ${s}</span>`).join('');
    }

    // Genre chips
    const genres = (prefs.entertainment && prefs.entertainment.favorite_genres) ? prefs.entertainment.favorite_genres : [];
    const genreEl = document.getElementById('prof-genre-chips');
    if (genreEl && genres.length > 0) {
      genreEl.innerHTML = genres.map(g => `<span class="tag-chip">${g}</span>`).join('');
    }
  }

  function renderAboutAI(asst) {
    if (!asst) return;
    const nameEl = document.getElementById('about-ai-name');
    if (nameEl && asst.name) nameEl.innerText = asst.name;
  }

  async function loadStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      cachedStatus = data;

      // Update overview metrics
      document.getElementById('disp-username').innerText = data.config.user_name || 'Timilehin';
      document.getElementById('disp-assistant').innerText = data.config.assistant_name || 'Nova';
      document.getElementById('disp-timers').innerText = data.active_timers || 0;
      document.getElementById('disp-power').innerText = data.state.power_source ? (data.state.power_source.toUpperCase()) : 'GRID';

      // Update config inputs
      document.getElementById('cfg-username').value = data.config.user_name || '';
      document.getElementById('cfg-assistant').value = data.config.assistant_name || '';
      document.getElementById('cfg-greeting').value = data.config.greeting_text || '';
      document.getElementById('cfg-macs').value = (data.config.mac_addresses || []).join(', ');

      // Render Active Timers
      renderActiveTimers(data.active_timers_list || []);

      // Render User Profile & AI Dossier
      renderUserProfile(data.memory || {});
      renderAboutAI(data.assistant || {});

      // Update models table
      const mb = document.getElementById('models-table-body');
      mb.innerHTML = `
        <tr>
          <td><strong>LLM Brain (3B)</strong></td>
          <td>Llama-3.2-3B-Instruct (GGUF)</td>
          <td>${data.models.llm_3b.complete ? '<span class="badge badge-green">Ready (Active)</span>' : (data.models.llm_3b.exists ? '<span class="badge badge-gray">Downloading...</span>' : '<span class="badge badge-gray">Not Downloaded</span>')}</td>
          <td>${(data.models.llm_3b.size_bytes / (1024*1024)).toFixed(1)} MB</td>
        </tr>
        <tr>
          <td><strong>LLM Brain (1B Fallback)</strong></td>
          <td>Llama-3.2-1B-Instruct (GGUF)</td>
          <td>${data.models.llm_1b.complete ? '<span class="badge badge-green">Downloaded</span>' : '<span class="badge badge-gray">Not Found</span>'}</td>
          <td>${(data.models.llm_1b.size_bytes / (1024*1024)).toFixed(1)} MB</td>
        </tr>
        <tr>
          <td><strong>STT Ears</strong></td>
          <td>Faster-Whisper small.en</td>
          <td>${data.models.stt.complete ? '<span class="badge badge-green">Ready (Active)</span>' : '<span class="badge badge-gray">Incomplete</span>'}</td>
          <td>${(data.models.stt.size_bytes / (1024*1024)).toFixed(1)} MB</td>
        </tr>
        <tr>
          <td><strong>TTS Voice</strong></td>
          <td>Piper Neural Voice / macOS say</td>
          <td>${data.models.tts.complete ? '<span class="badge badge-green">Ready (Active)</span>' : '<span class="badge badge-gray">macOS Say Fallback</span>'}</td>
          <td>${(data.models.tts.size_bytes / (1024*1024)).toFixed(1)} MB</td>
        </tr>
      `;

      // Update Memory facts table
      const facts = data.memory.learned_facts || [];
      const memBody = document.getElementById('memory-table-body');
      if (facts.length === 0) {
        memBody.innerHTML = `<tr><td colspan="3" style="text-align:center; opacity:0.6;">No facts saved yet. Add one above or tell the assistant "remember that..."</td></tr>`;
      } else {
        memBody.innerHTML = facts.map((fact, idx) => `
          <tr>
            <td>${idx + 1}</td>
            <td>${fact}</td>
            <td style="text-align:right;">
              <button class="btn btn-danger" style="padding:4px 8px; font-size:11px;" onclick="deleteFact(${idx})">Delete</button>
            </td>
          </tr>
        `).join('');
      }

    } catch (e) {
      console.error('Failed to load status:', e);
    }
  }

  async function saveConfig(e) {
    e.preventDefault();
    const macs = document.getElementById('cfg-macs').value.split(',').map(m => m.trim()).filter(Boolean);
    const body = {
      user_name: document.getElementById('cfg-username').value.trim(),
      assistant_name: document.getElementById('cfg-assistant').value.trim(),
      greeting_text: document.getElementById('cfg-greeting').value.trim(),
      mac_addresses: macs
    };

    const res = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (res.ok) {
      showToast('Configuration updated!');
      loadStatus();
    }
  }

  async function addFact() {
    const inp = document.getElementById('new-fact-input');
    const val = inp.value.trim();
    if (!val) return;

    const res = await fetch('/api/memory', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'add', fact: val})
    });
    if (res.ok) {
      inp.value = '';
      showToast('Fact added to memory!');
      loadStatus();
    }
  }

  async function deleteFact(idx) {
    if (!confirm('Delete this learned fact?')) return;
    const res = await fetch('/api/memory', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'delete', index: idx})
    });
    if (res.ok) {
      showToast('Fact removed.');
      loadStatus();
    }
  }

  async function setTimerSeconds() {
    const sec = document.getElementById('alarm-seconds').value;
    if (!sec) return;
    const res = await fetch('/api/timer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({seconds: parseFloat(sec), label: 'alarm'})
    });
    const data = await res.json();
    showToast(data.message || 'Timer set');
    document.getElementById('alarm-seconds').value = '';
    loadStatus();
  }

  async function setClockAlarm() {
    const clock = document.getElementById('alarm-clock').value;
    if (!clock) return;
    const res = await fetch('/api/timer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({clock_time: clock, label: 'alarm'})
    });
    const data = await res.json();
    showToast(data.message || 'Alarm set');
    document.getElementById('alarm-clock').value = '';
    loadStatus();
  }

  async function testChime() {
    showToast('Triggering alarm chime...');
    await fetch('/api/test-chime');
  }

  function toggleQuickActions() {
    const menu = document.getElementById('quick-actions-menu');
    menu.classList.toggle('show');
  }

  function insertPrompt(text) {
    const inp = document.getElementById('chat-input');
    inp.value = text;
    document.getElementById('quick-actions-menu').classList.remove('show');
    inp.focus();
    autoResizeTextarea(inp);
  }

  function handlePromptKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitPrompt();
    }
  }

  function autoResizeTextarea(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  function toggleThinking(btn) {
    const chevron = btn.querySelector('.thinking-chevron');
    const drawer = btn.nextElementSibling;
    chevron.classList.toggle('open');
    drawer.classList.toggle('open');
  }

  let lastUserQuery = '';

  function copyText(encoded, btn) {
    const text = decodeURIComponent(encoded);
    navigator.clipboard.writeText(text).then(() => {
      showToast("Copied to clipboard!");
      const original = btn.innerHTML;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
      setTimeout(() => btn.innerHTML = original, 1800);
    });
  }

  function triggerFollowUp(encoded) {
    const text = decodeURIComponent(encoded);
    const inp = document.getElementById('chat-input');
    inp.value = text;
    submitPrompt();
  }

  function getFollowUps(userMsg) {
    const lower = userMsg.toLowerCase();
    if (lower.includes('alarm') || lower.includes('timer')) {
      return ["Play an alarm sound in 30 seconds", "Set alarm for 7:30 AM", "How many active timers?"];
    }
    if (lower.includes('name') || lower.includes('call me') || lower.includes('address me')) {
      return ["What is your name?", "What do you remember about me?"];
    }
    if (lower.includes('movie') || lower.includes('silo') || lower.includes('merlin')) {
      return ["Tell me about Silo", "Who is Arthur in Merlin?", "What do I like to watch?"];
    }
    if (lower.includes('power') || lower.includes('grid') || lower.includes('battery')) {
      return ["What power source are we using?", "Is the grid active?"];
    }
    return ["Give me two reasons why sleep is important", "Set an alarm for 10 minutes", "Who is in Merlin?"];
  }

  function streamMessage(container, fullText, followUps = [], sourceTag = "Llama 3.2 3B") {
    const msgEl = document.createElement('div');
    msgEl.className = 'chat-msg assistant';

    // 1. Thinking State (Component 02 from beautifului.dev)
    const thinkingHtml = `
      <div class="thinking-container">
        <button type="button" class="thinking-btn" onclick="toggleThinking(this)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="var(--ink-2)"><path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"></path></svg>
          <span class="shimmer-text">Thinking Trace</span>
          <svg class="thinking-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"></path></svg>
        </button>
        <div class="thinking-drawer">
          <div class="trace-step"><span class="trace-dot"></span> Evaluated agent intent router (Timer, Identity, Memory)</div>
          <div class="trace-step"><span class="trace-dot"></span> Injected household state and personal memories</div>
          <div class="trace-step"><span class="trace-dot"></span> Routed to: <strong>${sourceTag}</strong></div>
        </div>
      </div>
    `;

    const tagHtml = `<div style="margin-bottom:6px;"><span class="source-chip"><svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"></circle></svg> ${sourceTag}</span></div>`;
    msgEl.innerHTML = `${thinkingHtml}${tagHtml}<span class="msg-content"></span><span class="streaming-cursor"></span>`;
    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;

    const contentEl = msgEl.querySelector('.msg-content');
    const cursorEl = msgEl.querySelector('.streaming-cursor');
    const words = fullText.split(' ');
    let wordIdx = 0;

    const interval = setInterval(() => {
      if (wordIdx < words.length) {
        contentEl.innerText += (wordIdx === 0 ? '' : ' ') + words[wordIdx];
        wordIdx++;
        container.scrollTop = container.scrollHeight;
      } else {
        clearInterval(interval);
        cursorEl.remove();

        // 2. Render Action Icons (Component 03: Copy, Retry, Feedback from beautifului.dev)
        const actionsRow = document.createElement('div');
        actionsRow.className = 'chat-actions-row ready';
        actionsRow.innerHTML = `
          <button class="action-icon-btn" title="Copy reply" onclick="copyText('${encodeURIComponent(fullText)}', this)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2.5"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
          <button class="action-icon-btn" title="Retry last query" onclick="retryLastQuery()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"></path></svg>
          </button>
          <button class="action-icon-btn" title="Helpful response" onclick="this.classList.toggle('active')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12M15 5.88L14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88z"></path></svg>
          </button>
          <button class="action-icon-btn" title="Not helpful" onclick="this.classList.toggle('active')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2M9 18.12L10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88z"></path></svg>
          </button>
        `;
        msgEl.appendChild(actionsRow);

        // 3. Render Follow-up Prompts
        if (followUps && followUps.length > 0) {
          const followUpsEl = document.createElement('div');
          followUpsEl.className = 'follow-ups-container ready';
          followUpsEl.innerHTML = `<div class="follow-ups-title">Suggested Follow-ups</div>` +
            followUps.map(f => `
              <button class="follow-up-btn" onclick="triggerFollowUp('${encodeURIComponent(f)}')">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><path d="M9 10l-5 5 5 5"></path><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg>
                ${f}
              </button>
            `).join('');
          msgEl.appendChild(followUpsEl);
        }

        container.scrollTop = container.scrollHeight;
      }
    }, 38);
  }

  function retryLastQuery() {
    if (lastUserQuery) {
      document.getElementById('chat-input').value = lastUserQuery;
      submitPrompt();
    }
  }

  async function submitPrompt() {
    const inp = document.getElementById('chat-input');
    const msg = inp.value.trim();
    if (!msg) return;

    lastUserQuery = msg;
    const container = document.getElementById('chat-msgs');
    container.innerHTML += `<div class="chat-msg user">${msg}</div>`;
    inp.value = '';
    inp.style.height = '28px';
    container.scrollTop = container.scrollHeight;

    // Show Loading State (Component 01 from beautifului.dev: 3x3 pixel grid + elapsed timer)
    const loaderId = 'loader-' + Date.now();
    const loaderEl = document.createElement('div');
    loaderEl.id = loaderId;
    loaderEl.className = 'chat-msg assistant';
    loaderEl.innerHTML = `
      <div class="loading-state-box">
        <div class="pixel-grid">
          <div class="pixel-dot"></div><div class="pixel-dot"></div><div class="pixel-dot"></div>
          <div class="pixel-dot"></div><div class="pixel-dot"></div><div class="pixel-dot"></div>
          <div class="pixel-dot"></div><div class="pixel-dot"></div><div class="pixel-dot"></div>
        </div>
        <span class="shimmer-text">Processing request...</span>
        <span class="font-mono" style="font-size:11px; opacity:0.6;" id="${loaderId}-timer">0.0s</span>
      </div>
    `;
    container.appendChild(loaderEl);
    container.scrollTop = container.scrollHeight;

    // Elapsed timer loop
    const startTime = Date.now();
    const elapsedInterval = setInterval(() => {
      const el = document.getElementById(`${loaderId}-timer`);
      if (el) {
        el.innerText = ((Date.now() - startTime) / 1000).toFixed(1) + 's';
      }
    }, 100);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg})
      });
      const data = await res.json();
      clearInterval(elapsedInterval);
      loaderEl.remove();

      const replyText = data.reply || 'No response received.';
      const followUps = getFollowUps(msg);
      const sourceTag = replyText.includes('Alarm set') || replyText.includes('Timer') ? 'Agent Tool: Timer' :
                       (replyText.includes('address you as') ? 'Agent Tool: Identity' :
                       (replyText.includes('remember') ? 'Agent Tool: Memory' : 'Local Brain: Llama 3.2 3B'));

      streamMessage(container, replyText, followUps, sourceTag);
      loadStatus();
    } catch (e) {
      clearInterval(elapsedInterval);
      loaderEl.remove();
      container.innerHTML += `<div class="chat-msg assistant">Error communicating with assistant: ${e.message}</div>`;
    }
  }

  // Close quick actions on outside click
  document.addEventListener('click', (e) => {
    const popover = document.getElementById('quick-actions-menu');
    if (popover && !e.target.closest('.prompt-bar-card')) {
      popover.classList.remove('show');
    }
  });

  // Initial load
  loadStatus();
  setInterval(loadStatus, 10000);
