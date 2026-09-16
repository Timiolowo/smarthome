/* ==========================================================================
   CHAT — Chat Console, Prompt Submission & Message Bubbles
   ========================================================================== */

function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}
window.autoResizeTextarea = autoResizeTextarea;

function insertPrompt(text) {
  const inp = document.getElementById('chat-input');
  if (!inp) return;
  inp.value = text;
  inp.focus();
  autoResizeTextarea(inp);
}
window.insertPrompt = insertPrompt;

function handlePromptKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    submitPrompt();
  }
}
window.handlePromptKey = handlePromptKey;

function copyText(encoded, btn) {
  const text = decodeURIComponent(encoded);
  navigator.clipboard.writeText(text).then(() => {
    if (typeof showSonner === 'function') showSonner('Copied to clipboard');
  });
}
window.copyText = copyText;

function triggerFollowUp(encoded) {
  const text = decodeURIComponent(encoded);
  const inp = document.getElementById('chat-input');
  if (inp) {
    inp.value = text;
    submitPrompt();
  }
}
window.triggerFollowUp = triggerFollowUp;

async function submitPrompt() {
  const inp = document.getElementById('chat-input');
  const msg = inp.value.trim();
  if (!msg) return;

  lastUserQuery = msg;
  const container = document.getElementById('chat-msgs');
  const timeStr = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

  // Render User Chat Bubble (daisyUI chat-start / chat-end)
  const userWrap = document.createElement('div');
  userWrap.className = 'chat-bubble-wrap user';
  userWrap.innerHTML = `
    <div class="chat-bubble">${msg}</div>
    <div class="chat-time">${timeStr}</div>
  `;
  container.appendChild(userWrap);
  inp.value = '';
  inp.style.height = 'auto';
  container.scrollTop = container.scrollHeight;

  // Render Assistant Skeleton Placeholder
  const loaderId = 'loader-' + Date.now();
  const loaderWrap = document.createElement('div');
  loaderWrap.id = loaderId;
  loaderWrap.className = 'chat-bubble-wrap assistant';
  loaderWrap.innerHTML = `
    <div class="skeleton" style="height:48px; width:220px;"></div>
  `;
  container.appendChild(loaderWrap);
  container.scrollTop = container.scrollHeight;

  if (window.tarsController) {
    window.tarsController.setState('thinking');
  }

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      const errMsg = data.error || `HTTP ${res.status} error`;
      const errWrap = document.createElement('div');
      errWrap.className = 'chat-bubble-wrap assistant';
      errWrap.innerHTML = `
        <div class="chat-bubble" style="border-color:hsl(var(--destructive)/0.5); background:hsl(var(--destructive)/0.1); color:hsl(var(--destructive));">
          ⚠️ <strong>API Error:</strong> ${errMsg}
        </div>
      `;
      container.appendChild(errWrap);
      if (typeof window.showSonner === 'function') {
        window.showSonner('LLM / API Error', errMsg);
      }
      return;
    }

    const replyText = data.reply || 'No response received.';
    const isErrorReply = replyText.startsWith('Error:') || /rate limit/i.test(replyText);
    const asstWrap = document.createElement('div');
    asstWrap.className = 'chat-bubble-wrap assistant';
    asstWrap.innerHTML = `
      <div class="chat-bubble" ${isErrorReply ? 'style="border-color:hsl(var(--destructive)/0.5); background:hsl(var(--destructive)/0.1); color:hsl(var(--destructive));"' : ''}>${replyText}</div>
      <div style="display:flex; align-items:center; gap:0.5rem; margin-top:0.25rem;">
        <span class="chat-time">${timeStr}</span>
        <button class="btn btn-ghost btn-sm" style="padding:0.15rem 0.35rem; font-size:0.7rem;" onclick="copyText('${encodeURIComponent(replyText)}', this)">Copy</button>
      </div>
    `;
    container.appendChild(asstWrap);
    container.scrollTop = container.scrollHeight;

    if (isErrorReply && typeof window.showSonner === 'function') {
      window.showSonner('API Alert', replyText);
    }

    // Update Live Display HUD text if active
    const replyLine = document.getElementById('live-reply-text');
    if (replyLine) {
      replyLine.textContent = isErrorReply ? `⚠️ ${replyText}` : `"${cleanSpokenText(replyText)}"`;
    }

    if (/standby mode|sleeping display|ambient standby/i.test(replyText) || /^(?:go on standby|enter standby|standby|sleep|go to sleep)$/i.test(msg.trim())) {
      if (typeof window.showIosStandby === 'function') {
        setTimeout(() => window.showIosStandby(), 1000);
      }
    }

    loadStatus();
  } catch (e) {
    loaderWrap.remove();
    const errWrap = document.createElement('div');
    errWrap.className = 'chat-bubble-wrap assistant';
    errWrap.innerHTML = `
      <div class="chat-bubble" style="border-color:hsl(var(--destructive)/0.5); background:hsl(var(--destructive)/0.1); color:hsl(var(--destructive));">⚠️ Error communicating with assistant: ${e.message}</div>
    `;
    container.appendChild(errWrap);
    if (typeof window.showSonner === 'function') {
      window.showSonner('Connection Error', e.message);
    }
  }
}
window.submitPrompt = submitPrompt;
