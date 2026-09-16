/**
 * ==========================================================================
 * LIVE TERMINAL UI CONTROLLER
 * Real-time terminal streaming, log filtering, command submission & modal states
 * ==========================================================================
 */

let isTerminalModalOpen = false;
let terminalPollInterval = null;
let terminalAutoScroll = true;
let terminalCurrentFilter = 'all';
let terminalLastLogId = 0;
let terminalCachedLogs = [];

function toggleTerminalModal(open) {
  const dialog = document.getElementById('terminal-modal-dialog');
  const navBtn = document.getElementById('btn-tars-terminal-toggle');
  if (!dialog) return;

  isTerminalModalOpen = open !== undefined ? open : !dialog.classList.contains('open');
  if (isTerminalModalOpen) {
    dialog.classList.add('open');
    if (navBtn) navBtn.classList.add('active');
    fetchTerminalLogs(true);
    if (!terminalPollInterval) {
      terminalPollInterval = setInterval(() => fetchTerminalLogs(false), 700);
    }
    const input = document.getElementById('terminal-cli-input');
    if (input) setTimeout(() => input.focus(), 150);
  } else {
    dialog.classList.remove('open');
    if (navBtn) navBtn.classList.remove('active');
    if (terminalPollInterval) {
      clearInterval(terminalPollInterval);
      terminalPollInterval = null;
    }
  }
}
window.toggleTerminalModal = toggleTerminalModal;

function toggleTerminalFullscreen() {
  const box = document.querySelector('.terminal-modal-box');
  if (box) box.classList.toggle('fullscreen');
}
window.toggleTerminalFullscreen = toggleTerminalFullscreen;

function toggleTerminalAutoScroll() {
  terminalAutoScroll = !terminalAutoScroll;
  const btn = document.getElementById('btn-terminal-autoscroll');
  if (btn) btn.classList.toggle('active', terminalAutoScroll);
}
window.toggleTerminalAutoScroll = toggleTerminalAutoScroll;

function filterTerminalLogs(val) {
  terminalCurrentFilter = val || 'all';
  renderTerminalLogs();
}
window.filterTerminalLogs = filterTerminalLogs;

async function copyTerminalLogs() {
  if (!terminalCachedLogs || terminalCachedLogs.length === 0) {
    if (typeof showSonner === 'function') {
      showSonner('Terminal', 'No logs to copy');
    }
    return;
  }

  let filtered = terminalCachedLogs;
  if (terminalCurrentFilter === 'voice') {
    filtered = filtered.filter(l => l.type === 'heard' || l.type === 'assistant');
  } else if (terminalCurrentFilter === 'system') {
    filtered = filtered.filter(l => l.type === 'system' || l.type === 'power_on' || l.type === 'power_off' || l.type === 'standby');
  } else if (terminalCurrentFilter === 'error') {
    filtered = filtered.filter(l => l.type === 'error' || l.level === 'error');
  }

  const textToCopy = filtered.map(item => `[${item.timestamp}] ${item.text}`).join('\n');

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(textToCopy);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = textToCopy;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }

    const copyBtn = document.getElementById('btn-terminal-copy');
    const label = document.getElementById('terminal-copy-label');
    if (label) label.textContent = 'Copied!';
    if (copyBtn) copyBtn.classList.add('active');

    setTimeout(() => {
      if (label) label.textContent = 'Copy';
      if (copyBtn) copyBtn.classList.remove('active');
    }, 2000);

    if (typeof showSonner === 'function') {
      showSonner('Terminal Logs Copied', `Copied ${filtered.length} log lines to clipboard.`);
    }
  } catch (err) {
    console.warn('Failed to copy terminal logs:', err);
    if (typeof showSonner === 'function') {
      showSonner('Copy Failed', 'Could not copy to clipboard.');
    }
  }
}
window.copyTerminalLogs = copyTerminalLogs;

async function clearTerminalLogs() {
  try {
    await fetch('/api/terminal/clear', { method: 'POST' });
    terminalCachedLogs = [];
    terminalLastLogId = 0;
    renderTerminalLogs();
  } catch (e) {
    console.warn('Failed to clear terminal logs:', e);
  }
}
window.clearTerminalLogs = clearTerminalLogs;

async function fetchTerminalLogs(forceFull = false) {
  try {
    const url = forceFull || terminalLastLogId === 0
      ? '/api/terminal/logs?limit=250'
      : `/api/terminal/logs?limit=100&since_id=${terminalLastLogId}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    if (data.ok && Array.isArray(data.logs)) {
      if (forceFull || terminalLastLogId === 0) {
        terminalCachedLogs = data.logs;
      } else if (data.logs.length > 0) {
        terminalCachedLogs = terminalCachedLogs.concat(data.logs);
        if (terminalCachedLogs.length > 500) {
          terminalCachedLogs = terminalCachedLogs.slice(-500);
        }
      }
      if (data.logs.length > 0) {
        terminalLastLogId = data.logs[data.logs.length - 1].id || terminalLastLogId;
      }
      renderTerminalLogs();
    }
  } catch (e) {
    console.warn('fetchTerminalLogs error:', e);
  }
}

function renderTerminalLogs() {
  const container = document.getElementById('terminal-log-entries');
  if (!container) return;

  let filtered = terminalCachedLogs;
  if (terminalCurrentFilter === 'voice') {
    filtered = filtered.filter(l => l.type === 'heard' || l.type === 'assistant');
  } else if (terminalCurrentFilter === 'system') {
    filtered = filtered.filter(l => l.type === 'system' || l.type === 'power_on' || l.type === 'power_off' || l.type === 'standby');
  } else if (terminalCurrentFilter === 'error') {
    filtered = filtered.filter(l => l.type === 'error' || l.level === 'error');
  }

  const escapeHtml = (str) => String(str || '').replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));

  container.innerHTML = filtered.map(item => {
    const typeClass = `t-${item.type || 'info'}`;
    return `
      <div class="terminal-line ${typeClass}">
        <span class="t-time-stamp">[${escapeHtml(item.timestamp)}]</span>
        <span class="t-line-text">${escapeHtml(item.text)}</span>
      </div>
    `;
  }).join('');

  if (terminalAutoScroll) {
    const screen = document.getElementById('terminal-screen-output');
    if (screen) {
      screen.scrollTop = screen.scrollHeight;
    }
  }
}

async function submitTerminalCommand(event) {
  if (event) event.preventDefault();
  const input = document.getElementById('terminal-cli-input');
  if (!input) return;

  const cmd = input.value.trim();
  if (!cmd) return;

  input.value = '';

  // Local echo
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  terminalCachedLogs.push({
    id: ++terminalLastLogId,
    timestamp: now,
    text: `👉 [Command]: "${cmd}"`,
    type: 'command',
    level: 'info'
  });
  renderTerminalLogs();

  try {
    const res = await fetch('/api/terminal/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd })
    });
    const data = await res.json();
    if (data.ok && data.reply) {
      const asstName = (window.cachedStatus?.assistant?.name || window.cachedStatus?.config?.assistant_name || 'Nova');
      terminalCachedLogs.push({
        id: ++terminalLastLogId,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        text: `🤖 [${asstName}]: "${data.reply}"`,
        type: 'assistant',
        level: 'info'
      });
      renderTerminalLogs();
    }
  } catch (err) {
    terminalCachedLogs.push({
      id: ++terminalLastLogId,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      text: `❌ Error executing command: ${err.message}`,
      type: 'error',
      level: 'error'
    });
    renderTerminalLogs();
  }
}
window.submitTerminalCommand = submitTerminalCommand;

// Global ESC shortcut to dismiss modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && isTerminalModalOpen) {
    toggleTerminalModal(false);
  }
});
