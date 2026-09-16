/* ==========================================================================
   TIMERS — Countdown Rendering, Timer API & Alarm Controls
   ========================================================================== */

function formatTimeRemaining(totalSec) {
  if (totalSec <= 0) return '0s left';
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
  if (pill) pill.innerText = `${count} Active`;
  if (cancelAllBtn) cancelAllBtn.style.display = count > 1 ? 'inline-flex' : 'none';
  if (overviewTimersBadge) overviewTimersBadge.innerText = count;

  if (sidebarBadge) {
    sidebarBadge.innerText = count;
    sidebarBadge.style.display = count > 0 ? 'inline-flex' : 'none';
  }

  if (!container) return;

  if (count === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">${ICONS.clock}</div>
        <div class="empty-state-title">No Active Timers</div>
        <div class="empty-state-desc">Set a timer or alarm using the panel above or by voice.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = activeTimersCache.map(t => {
    const remText = formatTimeRemaining(t.remaining_seconds);
    const pct = Math.max(0, Math.min(100, t.progress_pct || 0));
    return `
      <div class="card card-spotlight" id="timer-card-${t.id}" style="margin-bottom:0.75rem;">
        <div class="card-header" style="padding:1rem 1.25rem 0.5rem;">
          <div class="card-title-group">
            <div class="card-title" style="font-size:0.95rem;">
              <span style="color:hsl(var(--accent));">${ICONS.clock}</span>
              <span>${(t.label || 'Alarm').toUpperCase()}</span>
              <span class="badge badge-outline" style="font-size:0.7rem; font-family:var(--font-mono);">${t.display_time}</span>
            </div>
            <div class="card-description">Target: ${t.target_display || 'Scheduled'}</div>
          </div>
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="badge badge-warning" id="timer-rem-${t.id}">
              <span class="status-indicator-dot pulse"></span>
              ${remText}
            </span>
            <button class="btn btn-outline btn-sm" onclick="cancelTimer('${t.id}')">Cancel</button>
          </div>
        </div>
        <div class="card-content" style="padding:0 1.25rem 1rem;">
          <div style="width:100%; height:4px; background:hsl(var(--secondary)); border-radius:9999px; overflow:hidden; margin-top:0.5rem;">
            <div id="timer-bar-${t.id}" style="width:${pct}%; height:100%; background:hsl(var(--accent)); transition:width 1s linear;"></div>
          </div>
        </div>
      </div>
    `;
  }).join('');

  initCardSpotlight();
}

function tickActiveTimers() {
  if (!activeTimersCache || activeTimersCache.length === 0) return;
  let anyExpired = false;

  activeTimersCache.forEach(t => {
    t.remaining_seconds = Math.max(0, t.remaining_seconds - 1);
    const remEl = document.getElementById(`timer-rem-${t.id}`);
    const barEl = document.getElementById(`timer-bar-${t.id}`);

    if (remEl) {
      remEl.innerHTML = `<span class="status-indicator-dot pulse"></span> ${formatTimeRemaining(t.remaining_seconds)}`;
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
    showSonner(data.message || 'Timer canceled');
    loadStatus();
  } catch (e) {
    showSonner('Failed to cancel timer');
  }
}
window.cancelTimer = cancelTimer;

async function cancelAllTimers() {
  if (!confirm('Cancel all active timers?')) return;
  try {
    const res = await fetch('/api/timer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'cancel_all'})
    });
    const data = await res.json();
    showSonner(data.message || 'All timers canceled');
    loadStatus();
  } catch (e) {
    showSonner('Failed to cancel timers');
  }
}
window.cancelAllTimers = cancelAllTimers;

async function setTimerSeconds() {
  const sec = document.getElementById('alarm-seconds').value;
  if (!sec) return;
  const res = await fetch('/api/timer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({seconds: parseFloat(sec), label: 'alarm'})
  });
  const data = await res.json();
  showSonner('Timer Scheduled', data.message || 'Timer active');
  document.getElementById('alarm-seconds').value = '';
  loadStatus();
}
window.setTimerSeconds = setTimerSeconds;

async function setClockAlarm() {
  const clock = document.getElementById('alarm-clock').value;
  if (!clock) return;
  const res = await fetch('/api/timer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({clock_time: clock, label: 'alarm'})
  });
  const data = await res.json();
  showSonner('Alarm Set', data.message || 'Alarm active');
  document.getElementById('alarm-clock').value = '';
  loadStatus();
}
window.setClockAlarm = setClockAlarm;

async function testChime() {
  showSonner('Triggering Chime', 'Playing test alarm chime through speakers.');
  await fetch('/api/test-chime');
}
window.testChime = testChime;
