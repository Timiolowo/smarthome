/* ==========================================================================
   STATUS — System Status Polling & Dashboard Updates
   ========================================================================== */

async function loadStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    cachedStatus = data;
    window.cachedStatus = data;

    // Overview metric cards & identity
    const uName = data.config?.user_name || data.user_profile?.name || 'Resident';
    const asstName = data.assistant?.name || data.config?.assistant_name || 'Nova';
    const dispUser = document.getElementById('disp-username');
    const dispAsst = document.getElementById('disp-assistant');
    const dispTimers = document.getElementById('disp-timers');
    const dispPower = document.getElementById('disp-power');
    const brandAsst = document.getElementById('brand-assistant-name');
    const aboutAiName = document.getElementById('about-ai-name');
    const userBtn = document.getElementById('nav-btn-user');
    const userAvatar = userBtn ? userBtn.querySelector('.dock-avatar-badge') : null;

    if (dispUser) dispUser.innerText = uName;
    if (dispAsst) dispAsst.innerText = asstName;
    if (brandAsst) brandAsst.innerText = asstName.toUpperCase();
    if (aboutAiName) aboutAiName.innerText = asstName;
    if (dispTimers) dispTimers.innerText = data.active_timers || 0;
    if (dispPower) dispPower.innerText = data.state?.power_source ? data.state.power_source.toUpperCase() : 'GRID';

    // Update document title
    document.title = `Smart Home AI — ${asstName}`;

    if (userBtn) userBtn.title = `User Profile: ${uName}`;
    if (userAvatar && uName) {
      const parts = uName.trim().split(/\s+/);
      const initials = parts.length > 1 ? (parts[0][0] + parts[1][0]).toUpperCase() : uName.slice(0, 2).toUpperCase();
      userAvatar.textContent = initials;
    }

    // Dynamic Standby caption & overlays
    const standbyCaption = document.getElementById('standby-status-caption');
    if (standbyCaption) {
      standbyCaption.textContent = `WAITING FOR ${asstName.toUpperCase()} · SAY "HEY ${asstName.toUpperCase()}" OR CLICK TO WAKE`;
    }
    const standbyOverlay = document.getElementById('tars-ios-standby');
    if (standbyOverlay) {
      standbyOverlay.title = `Tap anywhere to wake ${asstName}`;
    }

    // Dynamic AI Architecture dossier & prompt info
    const dossierTitle = document.getElementById('about-ai-dossier-title');
    if (dossierTitle) dossierTitle.innerText = `${asstName} Assistant Dossier`;
    const directivesDesc = document.getElementById('about-ai-directives-desc');
    if (directivesDesc) directivesDesc.innerText = `Core operational directives programmed into ${asstName}'s system prompt.`;

    // Dynamic Chat controls
    const chatInterrupt = document.getElementById('btn-chat-interrupt');
    if (chatInterrupt) chatInterrupt.title = `Stop ${asstName}'s current speech and response`;

    // Dynamic Terminal titles & prompt prefixes
    const termTitle = document.getElementById('terminal-modal-title-text');
    if (termTitle) termTitle.innerText = `${asstName.toLowerCase()}@smarthome: ~ (live stream)`;
    document.querySelectorAll('.terminal-prompt-prefix').forEach(el => {
      el.innerText = `${asstName.toLowerCase()}@smarthome:~$`;
    });
    const termOptVoice = document.getElementById('terminal-opt-voice');
    if (termOptVoice) termOptVoice.innerText = `Voice Only (Heard/${asstName})`;

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

    // Protect config form inputs from being clobbered during background polling
    const configForm = document.getElementById('config-form');
    const isUserFocusInForm = configForm && configForm.contains(document.activeElement);

    if (!isUserFocusInForm && !window.__configFormHasUnsavedEdits) {
      const cfgUser = document.getElementById('cfg-username');
      const cfgAsst = document.getElementById('cfg-assistant');
      const cfgGreet = document.getElementById('cfg-greeting');
      const cfgMacs = document.getElementById('cfg-macs');
      const cfgPhoneIp = document.getElementById('cfg-phone-ip');

      if (cfgUser && (!cfgUser.value || !window.__configFormInitialized)) cfgUser.value = uName;
      if (cfgAsst && (!cfgAsst.value || !window.__configFormInitialized)) cfgAsst.value = asstName;
      if (cfgGreet && (!cfgGreet.value || !window.__configFormInitialized)) cfgGreet.value = data.config.greeting_text || '';
      if (cfgMacs && (!cfgMacs.value || !window.__configFormInitialized)) cfgMacs.value = (data.config.mac_addresses || []).join(', ');
      if (cfgPhoneIp && (!cfgPhoneIp.value || !window.__configFormInitialized)) cfgPhoneIp.value = data.config.phone_ip || '';

      // Only set provider & keys on initial load or clean reload
      if (!window.__configFormInitialized) {
        const llmProv = data.config.llm_provider || 'local';
        const provEl = document.getElementById('cfg-llm-provider');
        if (provEl) provEl.value = llmProv;

        const modelEl = document.getElementById('cfg-llm-model');
        if (modelEl) modelEl.value = data.config.llm_model || '';

        const keyEl = document.getElementById('cfg-llm-api-key');
        if (keyEl && data.config.llm_api_key) keyEl.value = data.config.llm_api_key;

        const urlEl = document.getElementById('cfg-llm-base-url');
        if (urlEl) urlEl.value = data.config.llm_base_url || '';

        handleLLMProviderChange();
        window.__configFormInitialized = true;
      }
    }

    // Location & Timezone badges in About Me settings
    const profLocBadge = document.getElementById('prof-location-badge');
    const profTzBadge = document.getElementById('prof-timezone-badge');
    if (profLocBadge && data.memory?.profile?.location) {
      profLocBadge.innerText = data.memory.profile.location;
    }
    if (profTzBadge && data.memory?.profile?.timezone) {
      profTzBadge.innerText = data.memory.profile.timezone;
    }

    // Provider badge & System Status Widget readout
    const badgeEl = document.getElementById('cfg-active-provider-badge');
    if (badgeEl && data.llm_provider) {
      badgeEl.textContent = `${data.llm_provider.provider} (${data.llm_provider.model})`;
      badgeEl.className = data.llm_provider.available ? 'badge badge-success' : 'badge badge-outline';
    }

    const modelEl = document.getElementById('tars-model-val');
    const reasoningEl = document.getElementById('tars-reasoning-val');
    if (data.llm_provider) {
      const pName = data.llm_provider.provider || 'Local';
      const mName = data.llm_provider.model || 'Llama 3.2';
      const isLive = data.llm_provider.available;

      if (modelEl) {
        modelEl.textContent = mName;
        modelEl.className = isLive ? 'system-readout-val active' : 'system-readout-val';
      }
      if (reasoningEl) {
        reasoningEl.textContent = `${pName.toLowerCase()} · ${isLive ? 'active' : 'offline'}`;
        reasoningEl.className = isLive ? 'system-readout-val ok' : 'system-readout-val';
      }
    }

    // Timers, Reminders & Dossier
    renderActiveTimers(data.active_timers_list || []);
    if (typeof renderActiveReminders === 'function') {
      renderActiveReminders(data.active_reminders_list || []);
    }
    renderUserProfile(data.memory || {});
    renderAboutAI(data.assistant || {});

    // Models Table
    const mb = document.getElementById('models-table-body');
    if (mb) {
      const isLocal = (data.config.llm_provider || 'local') === 'local';
      mb.innerHTML = `
        <tr style="border-bottom:1px solid hsl(var(--border));">
          <td style="padding:0.75rem 0.5rem; font-weight:600;">LLM Brain (${data.llm_provider ? data.llm_provider.provider : 'Local'})</td>
          <td style="padding:0.75rem 0.5rem; font-family:var(--font-mono); font-size:0.8rem;">${data.llm_provider ? data.llm_provider.model : 'Llama-3.2-3B-Instruct'}</td>
          <td style="padding:0.75rem 0.5rem;">${data.llm_provider && data.llm_provider.available ? '<span class="badge badge-success">Ready</span>' : '<span class="badge badge-outline">Standby</span>'}</td>
          <td style="padding:0.75rem 0.5rem; color:hsl(var(--muted-foreground));">${isLocal ? ((data.models.llm_3b.size_bytes / (1024*1024)).toFixed(1) + ' MB') : 'Cloud API'}</td>
        </tr>
        <tr style="border-bottom:1px solid hsl(var(--border));">
          <td style="padding:0.75rem 0.5rem; font-weight:600;">STT Ears</td>
          <td style="padding:0.75rem 0.5rem; font-family:var(--font-mono); font-size:0.8rem;">Faster-Whisper small.en</td>
          <td style="padding:0.75rem 0.5rem;">${data.models.stt.complete ? '<span class="badge badge-success">Ready</span>' : '<span class="badge badge-outline">Incomplete</span>'}</td>
          <td style="padding:0.75rem 0.5rem; color:hsl(var(--muted-foreground));">${(data.models.stt.size_bytes / (1024*1024)).toFixed(1)} MB</td>
        </tr>
        <tr>
          <td style="padding:0.75rem 0.5rem; font-weight:600;">TTS Voice</td>
          <td style="padding:0.75rem 0.5rem; font-family:var(--font-mono); font-size:0.8rem;">Piper Neural / macOS say</td>
          <td style="padding:0.75rem 0.5rem;">${data.models.tts.complete ? '<span class="badge badge-success">Ready</span>' : '<span class="badge badge-outline">macOS Say</span>'}</td>
          <td style="padding:0.75rem 0.5rem; color:hsl(var(--muted-foreground));">${(data.models.tts.size_bytes / (1024*1024)).toFixed(1)} MB</td>
        </tr>
      `;
    }

    // Memory facts
    const facts = data.memory.learned_facts || [];
    const memBody = document.getElementById('memory-table-body');
    if (memBody) {
      if (facts.length === 0) {
        memBody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding:1.5rem 0; color:hsl(var(--muted-foreground));">No facts saved yet. Add one above or tell the assistant "remember that..."</td></tr>`;
      } else {
        memBody.innerHTML = facts.map((fact, idx) => `
          <tr style="border-bottom:1px solid hsl(var(--border));">
            <td style="padding:0.6rem 0.5rem; font-family:var(--font-mono); font-size:0.8rem; color:hsl(var(--muted-foreground));">${idx + 1}</td>
            <td style="padding:0.6rem 0.5rem;">${fact}</td>
            <td style="padding:0.6rem 0.5rem; text-align:right;">
              <button class="btn btn-outline btn-sm" onclick="deleteFact(${idx})">Delete</button>
            </td>
          </tr>
        `).join('');
      }
    }

  } catch (e) {
    console.error('Failed to load status:', e);
  }
}
window.loadStatus = loadStatus;

// Setup on load
document.addEventListener('DOMContentLoaded', () => {
  initCardSpotlight();
  if (typeof updateVoiceOutputUI === 'function') updateVoiceOutputUI();
  if (typeof updateContinuousModeUI === 'function') updateContinuousModeUI();

  const cfgForm = document.getElementById('config-form');
  if (cfgForm) {
    cfgForm.addEventListener('input', () => { window.__configFormHasUnsavedEdits = true; });
    cfgForm.addEventListener('change', () => { window.__configFormHasUnsavedEdits = true; });
  }

  loadStatus();
});

if (typeof updateVoiceOutputUI === 'function') updateVoiceOutputUI();
if (typeof updateContinuousModeUI === 'function') updateContinuousModeUI();
loadStatus();
setInterval(loadStatus, 10000);
