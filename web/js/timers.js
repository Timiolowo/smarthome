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

// =============================================================
// REMINDERS RENDERING & CONTROLS
// =============================================================
let activeRemindersCache = [];

function renderActiveReminders(reminders) {
  activeRemindersCache = reminders || [];
  const container = document.getElementById('alarms-active-reminders-container');
  const pill = document.getElementById('active-reminders-count-pill');
  const cancelAllBtn = document.getElementById('cancel-all-reminders-btn');

  const count = activeRemindersCache.length;
  if (pill) pill.innerText = `${count} Scheduled`;
  if (cancelAllBtn) cancelAllBtn.style.display = count > 1 ? 'inline-flex' : 'none';

  if (!container) return;

  if (count === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding:1.5rem 0; text-align:center;">
        <div class="empty-state-icon" style="color:hsl(var(--muted-foreground)); opacity:0.6; margin-bottom:0.4rem;">
          <svg class="icon-svg" style="width:28px; height:28px;" viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        </div>
        <div class="empty-state-title" style="font-size:0.9rem; font-weight:600;">No Scheduled Reminders</div>
        <div class="empty-state-desc" style="font-size:0.775rem; color:hsl(var(--muted-foreground));">
          Say <em>"Remind me tomorrow at 5pm to call mom"</em> or use the box above.
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = activeRemindersCache.map(r => {
    const isPast = r.target_timestamp && (r.target_timestamp < Date.now() / 1000);
    const timeDisplay = r.display_str || 'Scheduled';
    const taskTitle = r.task || 'Reminder';

    return `
      <div class="card card-spotlight" id="reminder-card-${r.id}" style="margin-bottom:0.75rem; background:hsl(var(--secondary)/0.4); border-radius:var(--radius);">
        <div class="card-header" style="padding:0.85rem 1.15rem; display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
          <div class="card-title-group" style="flex:1;">
            <div class="card-title" style="font-size:0.9rem; display:flex; align-items:center; gap:0.5rem;">
              <span style="color:hsl(var(--primary));">
                <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
              </span>
              <span style="font-weight:600; text-transform:capitalize;">${taskTitle}</span>
            </div>
            <div class="card-description" style="font-size:0.775rem; margin-top:0.2rem; color:hsl(var(--muted-foreground));">
              📅 ${timeDisplay}
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="badge ${isPast ? 'badge-destructive' : 'badge-primary'}" style="font-size:0.7rem;">
              ${isPast ? 'Due' : 'Upcoming'}
            </span>
            <button class="btn btn-ghost btn-sm" style="color:hsl(var(--destructive)); padding:0.25rem 0.5rem;" onclick="cancelReminder('${r.id}')" title="Delete Reminder">
              <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (typeof initCardSpotlight === 'function') initCardSpotlight();
}
window.renderActiveReminders = renderActiveReminders;

async function createManualReminder() {
  const inp = document.getElementById('input-new-reminder');
  if (!inp || !inp.value.trim()) return;
  const text = inp.value.trim();

  try {
    const res = await fetch('/api/reminders/create', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    const data = await res.json();
    if (data.ok) {
      if (typeof showSonner === 'function') showSonner('Reminder Scheduled', data.reply);
      inp.value = '';
      loadStatus();
    } else {
      if (typeof showSonner === 'function') showSonner('Could Not Schedule', data.error || 'Check reminder syntax');
    }
  } catch (e) {
    if (typeof showSonner === 'function') showSonner('Error', e.message);
  }
}
window.createManualReminder = createManualReminder;

async function cancelReminder(remId) {
  try {
    const res = await fetch('/api/reminders/cancel', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: remId})
    });
    const data = await res.json();
    if (data.ok) {
      if (typeof showSonner === 'function') showSonner('Reminder Deleted', 'Scheduled reminder was removed.');
      loadStatus();
    }
  } catch (e) {
    if (typeof showSonner === 'function') showSonner('Error', 'Failed to cancel reminder');
  }
}
window.cancelReminder = cancelReminder;

async function cancelAllReminders() {
  if (!confirm('Cancel all scheduled reminders?')) return;
  try {
    const res = await fetch('/api/reminders/cancel', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({all: true})
    });
    const data = await res.json();
    if (data.ok) {
      if (typeof showSonner === 'function') showSonner('Reminders Cleared', `Cleared ${data.cancelled || 0} reminders.`);
      loadStatus();
    }
  } catch (e) {
    if (typeof showSonner === 'function') showSonner('Error', 'Failed to clear reminders');
  }
}
window.cancelAllReminders = cancelAllReminders;

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
