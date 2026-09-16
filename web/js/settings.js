/* ==========================================================================
   SETTINGS — Configuration Form, LLM Provider & Location Permission
   ========================================================================== */

// 8. CONFIGURATION & LLM SELECTOR
function switchSettingsTab(tabKey, el) {
  const allBtns = document.querySelectorAll('.settings-subnav-btn');
  const allPanels = document.querySelectorAll('.settings-panel');

  allBtns.forEach(btn => btn.classList.remove('active'));
  allPanels.forEach(p => p.classList.remove('active'));

  const targetPanel = document.getElementById(`settings-panel-${tabKey}`);
  if (targetPanel) {
    targetPanel.classList.add('active');
  }

  if (el) {
    el.classList.add('active');
  } else {
    const matchingBtn = document.querySelector(`.settings-subnav-btn[onclick*="${tabKey}"]`);
    if (matchingBtn) matchingBtn.classList.add('active');
  }
}
window.switchSettingsTab = switchSettingsTab;

function handleLLMProviderChange() {
  const provSelect = document.getElementById('cfg-llm-provider');
  if (!provSelect) return;
  const val = provSelect.value;
  const cloudFields = document.getElementById('cfg-cloud-fields');
  const baseUrlGroup = document.getElementById('cfg-base-url-group');
  const modelInput = document.getElementById('cfg-llm-model');

  if (cloudFields) cloudFields.style.display = (val === 'local') ? 'none' : 'flex';
  if (baseUrlGroup) baseUrlGroup.style.display = (val === 'custom') ? 'flex' : 'none';

  const defaultModels = {
    gemini: 'gemini-2.5-flash',
    openai: 'gpt-4o-mini',
    groq: 'llama-3.3-70b-versatile',
    deepseek: 'deepseek-chat',
    custom: 'default'
  };

  const placeholders = {
    gemini: 'e.g. gemini-2.5-flash, gemini-2.5-pro',
    openai: 'e.g. gpt-4o, gpt-4o-mini, o3-mini',
    groq: 'e.g. llama-3.3-70b-versatile',
    deepseek: 'e.g. deepseek-chat, deepseek-reasoner',
    custom: 'e.g. meta-llama/llama-3.3-70b, mistral, etc.'
  };
  if (modelInput) {
    if (placeholders[val]) modelInput.placeholder = placeholders[val];
    if (!modelInput.value.trim() && defaultModels[val]) {
      modelInput.value = defaultModels[val];
    }
  }
}
window.handleLLMProviderChange = handleLLMProviderChange;

function toggleApiKeyVisibility() {
  const keyInput = document.getElementById('cfg-llm-api-key');
  const eyeIcon = document.getElementById('cfg-eye-icon');
  if (!keyInput) return;
  if (keyInput.type === 'password') {
    keyInput.type = 'text';
    if (eyeIcon) {
      eyeIcon.innerHTML = `
        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
        <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>
        <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>
        <line x1="2" x2="22" y1="2" y2="22"/>
      `;
    }
  } else {
    keyInput.type = 'password';
    if (eyeIcon) {
      eyeIcon.innerHTML = `
        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
        <circle cx="12" cy="12" r="3"/>
      `;
    }
  }
}
window.toggleApiKeyVisibility = toggleApiKeyVisibility;

async function saveConfig(e) {
  if (e) e.preventDefault();
  const macs = document.getElementById('cfg-macs') ? document.getElementById('cfg-macs').value.split(',').map(m => m.trim()).filter(Boolean) : [];
  const provVal = document.getElementById('cfg-llm-provider') ? document.getElementById('cfg-llm-provider').value : 'local';
  const phoneIp = document.getElementById('cfg-phone-ip') ? document.getElementById('cfg-phone-ip').value.trim() : '';
  const userBio = document.getElementById('cfg-user-bio') ? document.getElementById('cfg-user-bio').value.trim() : '';

  const body = {
    user_name: document.getElementById('cfg-username') ? document.getElementById('cfg-username').value.trim() : '',
    assistant_name: document.getElementById('cfg-assistant') ? document.getElementById('cfg-assistant').value.trim() : '',
    greeting_text: document.getElementById('cfg-greeting') ? document.getElementById('cfg-greeting').value.trim() : '',
    mac_addresses: macs,
    phone_ip: phoneIp,
    user_bio: userBio,
    llm_provider: provVal,
    llm_model: document.getElementById('cfg-llm-model') ? document.getElementById('cfg-llm-model').value.trim() : null,
    llm_api_key: document.getElementById('cfg-llm-api-key') ? document.getElementById('cfg-llm-api-key').value.trim() : null,
    llm_base_url: document.getElementById('cfg-llm-base-url') ? document.getElementById('cfg-llm-base-url').value.trim() : null,
    voice_name: document.getElementById('cfg-browser-voice') ? document.getElementById('cfg-browser-voice').value : 'default'
  };

  const res = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  if (res.ok) {
    window.__configFormHasUnsavedEdits = false;
    window.__configFormInitialized = false;
    showSonner('Configuration Saved', 'Assistant and LLM settings updated.');
    loadStatus();
  }
}
window.saveConfig = saveConfig;

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
    showSonner('Fact Memorized', 'Added to long-term memory store.');
    loadStatus();
  }
}
window.addFact = addFact;

async function deleteFact(idx) {
  if (!confirm('Delete this learned fact?')) return;
  const res = await fetch('/api/memory', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'delete', index: idx})
  });
  if (res.ok) {
    showSonner('Fact Removed');
    loadStatus();
  }
}
window.deleteFact = deleteFact;

// Location Permission & Detection
async function requestLocationPermission() {
  const locBadge = document.getElementById('prof-location-badge');
  const tzBadge = document.getElementById('prof-timezone-badge');
  const btnText = document.getElementById('btn-detect-location-text');
  const statusHint = document.getElementById('location-permission-status');

  if (btnText) btnText.textContent = 'Detecting...';
  if (statusHint) statusHint.textContent = 'Requesting browser geolocation permission...';

  if (!('geolocation' in navigator)) {
    if (locBadge) locBadge.innerText = 'Geolocation not supported';
    if (btnText) btnText.textContent = 'Unsupported';
    if (statusHint) statusHint.textContent = 'Your browser does not support geolocation.';
    return;
  }

  try {
    const pos = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000 });
    });

    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;

    // Set timezone from browser
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tzBadge) tzBadge.innerText = tz;

    // Reverse geocode to get city name
    let placeName = `${lat.toFixed(2)}, ${lon.toFixed(2)}`;
    try {
      const revRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
      if (revRes.ok) {
        const revData = await revRes.json();
        const addr = revData.address || {};
        const city = addr.city || addr.town || addr.suburb || addr.state || '';
        const country = addr.country || '';
        if (city) placeName = `${city}, ${country}`.trim();
      }
    } catch (_) {}

    if (locBadge) locBadge.innerText = placeName;
    if (btnText) btnText.textContent = 'Detected';
    if (statusHint) statusHint.textContent = `Location detected: ${placeName} (${tz})`;

    // Sync to backend
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location: placeName, timezone: tz, latitude: lat, longitude: lon })
      });
    } catch (_) {}

    if (typeof showSonner === 'function') {
      showSonner('Location Detected', placeName);
    }
  } catch (err) {
    if (btnText) btnText.textContent = 'Detect Location';
    if (err.code === 1) {
      if (locBadge) locBadge.innerText = 'Permission denied';
      if (statusHint) statusHint.textContent = 'Location permission denied. Click the browser lock icon in the address bar to allow.';
      if (typeof showSonner === 'function') {
        showSonner('Location Blocked', 'Please grant location access in your browser settings.');
      }
    } else {
      if (statusHint) statusHint.textContent = 'Could not detect location. Please try again.';
      if (typeof showSonner === 'function') {
        showSonner('Location Error', err.message || 'Failed to detect location.');
      }
    }
  }
}
window.requestLocationPermission = requestLocationPermission;
