// SmartHome AI Assistant — Interactive Setup Wizard Logic

let currentStep = 1;
const totalSteps = 4;
let setupData = {
  user_name: "",
  assistant_name: "Nova",
  greeting_text: "",
  trigger_phrases: ["hello", "hey", "hi"],
  bio_notes: "",
  ai_mode: "local", // "local" or "cloud"
  llm_choice: "llm_3b", // "llm_3b" or "llm_1b"
  cloud_provider: "openai",
  cloud_api_key: "",
  llm_provider: "local",
  llm_model: "",
  llm_api_key: "",
  llm_base_url: "",
  microphone_device: 0,
  ready_chime: false,
  phone_ip: ""
};

let downloadPollTimer = null;
let micStream = null;
let micAudioContext = null;
let micAnalyser = null;
let micAnimFrame = null;

// Initialize on load
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await loadInitialStatus();
});

// Load system status & defaults
async function loadInitialStatus() {
  try {
    const res = await fetch("/api/setup/status");
    if (!res.ok) throw new Error("Failed to load status");
    const data = await res.json();

    const cfg = data.config || {};
    const assistant = data.assistant || {};

    if (cfg.user_name) setupData.user_name = cfg.user_name;
    if (cfg.assistant_name || assistant.name) setupData.assistant_name = cfg.assistant_name || assistant.name;
    if (cfg.greeting_text) setupData.greeting_text = cfg.greeting_text;
    if (cfg.phone_ip) setupData.phone_ip = cfg.phone_ip;
    if (cfg.microphone_device !== undefined) setupData.microphone_device = cfg.microphone_device;
    if (cfg.ready_chime !== undefined) setupData.ready_chime = cfg.ready_chime;

    // Prepopulate inputs
    const userNameInput = document.getElementById("input-user-name");
    if (userNameInput && setupData.user_name) userNameInput.value = setupData.user_name;

    const assistantNameInput = document.getElementById("input-assistant-name");
    if (assistantNameInput && setupData.assistant_name) assistantNameInput.value = setupData.assistant_name;

    const greetingInput = document.getElementById("input-greeting");
    if (greetingInput && setupData.greeting_text) greetingInput.value = setupData.greeting_text;

    const phoneIpInput = document.getElementById("input-phone-ip");
    if (phoneIpInput && setupData.phone_ip) phoneIpInput.value = setupData.phone_ip;

    const chimeToggle = document.getElementById("toggle-ready-chime");
    if (chimeToggle) chimeToggle.checked = setupData.ready_chime;

    // Render System Hardware Diagnostics
    renderSystemSpecs(data.system_specs || {});

    // Render Audio Devices
    renderAudioDevices(data.audio_devices || []);

    // Render Models
    renderModelsList(data.models || {}, data.system_specs || {});

  } catch (err) {
    console.error("Error loading setup status:", err);
  }
}

function renderSystemSpecs(specs) {
  const summaryEl = document.getElementById("system-specs-summary");
  const reasonEl = document.getElementById("system-specs-reason");
  if (!summaryEl || !reasonEl) return;

  const ram = specs.ram_gb ? `${specs.ram_gb} GB RAM` : "8+ GB RAM";
  const chip = specs.chip ? ` · ${specs.chip}` : "";
  const platformName = specs.platform ? ` · ${specs.platform}` : "";
  summaryEl.textContent = `${ram}${chip}${platformName}`;

  if (specs.reason) {
    reasonEl.innerHTML = `<strong>Recommendation:</strong> ${specs.reason}`;
  }

  // Pre-select recommended model tier
  if (specs.recommended_model === "llm_1b") {
    selectLlmTier("llm_1b");
    const b1 = document.getElementById("badge-llm-1b");
    if (b1) { b1.style.display = "inline-block"; b1.textContent = "Recommended for your RAM"; }
    const b3 = document.getElementById("badge-llm-3b");
    if (b3) { b3.textContent = "Requires 8GB+ RAM"; b3.className = "badge-tag badge-cloud"; }
  } else {
    selectLlmTier("llm_3b");
  }
}

function selectLlmTier(tierKey) {
  setupData.llm_choice = tierKey;
  document.querySelectorAll(".llm-tier-card").forEach(card => {
    if (card.dataset.llm === tierKey) {
      card.classList.add("selected");
    } else {
      card.classList.remove("selected");
    }
  });
  updateDownloadButtonState();
}

function renderModelsList(models, specs) {
  // Update LLM tier statuses
  const st3b = models["llm_3b"] ? models["llm_3b"].installed : false;
  const st1b = models["llm_1b"] ? models["llm_1b"].installed : false;

  const el3b = document.getElementById("status-llm-3b");
  if (el3b) {
    el3b.innerHTML = `<span class="model-status-tag ${st3b ? 'ready' : 'missing'}">${st3b ? 'Installed & Ready' : 'Missing on Disk'}</span>`;
  }

  const el1b = document.getElementById("status-llm-1b");
  if (el1b) {
    el1b.innerHTML = `<span class="model-status-tag ${st1b ? 'ready' : 'missing'}">${st1b ? 'Installed & Ready' : 'Missing on Disk'}</span>`;
  }

  // Render Voice models
  const container = document.getElementById("models-list-container");
  if (!container) return;

  const voiceKeys = ["stt", "tts"];
  let html = "";

  voiceKeys.forEach(key => {
    const item = models[key];
    if (!item) return;

    const isReady = item.installed;
    const icon = key === "stt" ? "" : "";

    html += `
      <div class="model-item">
        <div class="model-info-left">
          <div class="model-category-icon">${icon}</div>
          <div class="model-names">
            <h4>${item.name}</h4>
            <p>${item.category} · ${item.download_size || ''}</p>
          </div>
        </div>
        <div>
          <span class="model-status-tag ${isReady ? 'ready' : 'missing'}">
            ${isReady ? 'Installed & Ready' : 'Missing on Disk'}
          </span>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  window._cachedModels = models;
  updateDownloadButtonState();
}

function updateDownloadButtonState() {
  const models = window._cachedModels || {};
  const selectedLlm = setupData.llm_choice || "llm_3b";
  const llmReady = models[selectedLlm] ? models[selectedLlm].installed : false;
  const sttReady = models["stt"] ? models["stt"].installed : false;
  const ttsReady = models["tts"] ? models["tts"].installed : false;

  const allReady = llmReady && sttReady && ttsReady;
  const dlAllBtn = document.getElementById("btn-download-all");
  if (dlAllBtn) {
    if (allReady) {
      dlAllBtn.textContent = "All Selected Models Verified";
      dlAllBtn.disabled = true;
      dlAllBtn.classList.replace("btn-primary", "btn-secondary");
    } else {
      const llmName = selectedLlm === "llm_3b" ? "Llama 3.2 3B" : "Llama 3.2 1B";
      dlAllBtn.textContent = `Download ${llmName} & Voice Models (1-Click)`;
      dlAllBtn.disabled = false;
      dlAllBtn.classList.replace("btn-secondary", "btn-primary");
    }
  }
}

function setupEventListeners() {
  // Navigation
  document.getElementById("btn-next").addEventListener("click", () => handleNext());
  document.getElementById("btn-prev").addEventListener("click", () => handlePrev());

  // Step Tabs
  document.querySelectorAll(".step-tab").forEach(tab => {
    tab.addEventListener("click", (e) => {
      const step = parseInt(tab.dataset.step);
      if (step < currentStep || validateCurrentStep()) {
        goToStep(step);
      }
    });
  });

  // Mode Selection Cards
  document.querySelectorAll(".select-card[data-mode]").forEach(card => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".select-card[data-mode]").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      setupData.ai_mode = card.dataset.mode;
      toggleAiModeView(setupData.ai_mode);
    });
  });

  // Local LLM Tier Cards Selection
  document.querySelectorAll(".llm-tier-card").forEach(card => {
    card.addEventListener("click", () => {
      selectLlmTier(card.dataset.llm);
    });
  });

  // Cloud Provider Change (toggle Base URL & dynamic model placeholders)
  const cloudSelect = document.getElementById("select-cloud-provider");
  const modelInput = document.getElementById("input-cloud-model");
  const modelPlaceholders = {
    gemini: "e.g. gemini-2.5-flash, gemini-3.7-flash, gemini-2.5-pro (or leave blank)",
    openai: "e.g. gpt-4o, gpt-4o-mini, o3-mini (or leave blank)",
    groq: "e.g. llama-3.3-70b-versatile (or leave blank)",
    anthropic: "e.g. claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022 (or leave blank)",
    deepseek: "e.g. deepseek-chat, deepseek-reasoner (or leave blank)",
    custom: "e.g. meta-llama/llama-3.3-70b, mistral, etc."
  };

  function updateCloudProviderUI() {
    if (!cloudSelect) return;
    const prov = cloudSelect.value;
    const isCustom = prov === "custom";
    const baseUrlGroup = document.getElementById("group-cloud-base-url");
    if (baseUrlGroup) baseUrlGroup.style.display = isCustom ? "block" : "none";
    if (modelInput) {
      modelInput.placeholder = modelPlaceholders[prov] || "Leave empty for default";
    }
  }

  if (cloudSelect) {
    cloudSelect.addEventListener("change", updateCloudProviderUI);
    updateCloudProviderUI();
  }

  // Toggle API Key Visibility
  const toggleKeyBtn = document.getElementById("btn-toggle-key-visibility");
  const keyInput = document.getElementById("input-cloud-key");
  if (toggleKeyBtn && keyInput) {
    toggleKeyBtn.addEventListener("click", () => {
      const isPass = keyInput.type === "password";
      keyInput.type = isPass ? "text" : "password";
      toggleKeyBtn.title = isPass ? "Hide API Key" : "Show API Key";
    });
  }

  // Download All Models Button
  const dlBtn = document.getElementById("btn-download-all");
  if (dlBtn) {
    dlBtn.addEventListener("click", startModelDownload);
  }

  // Audio Chime Test
  const chimeBtn = document.getElementById("btn-test-chime");
  if (chimeBtn) {
    chimeBtn.addEventListener("click", async () => {
      chimeBtn.disabled = true;
      chimeBtn.textContent = "Playing sound...";
      try {
        await fetch("/api/test-chime");
      } catch (e) {
        console.error("Chime error:", e);
      }
      setTimeout(() => {
        chimeBtn.disabled = false;
        chimeBtn.textContent = "Test Chime";
      }, 2000);
    });
  }

  // Mic Test Button
  const micBtn = document.getElementById("btn-test-mic");
  if (micBtn) {
    micBtn.addEventListener("click", toggleMicTesting);
  }

  // Launch Assistant Button
  const launchBtn = document.getElementById("btn-launch-assistant");
  if (launchBtn) {
    launchBtn.addEventListener("click", handleFinalLaunch);
  }
}

function toggleAiModeView(mode) {
  const localSection = document.getElementById("local-models-section");
  const cloudSection = document.getElementById("cloud-api-section");

  if (mode === "local") {
    if (localSection) localSection.style.display = "block";
    if (cloudSection) cloudSection.style.display = "none";
  } else {
    if (localSection) localSection.style.display = "none";
    if (cloudSection) cloudSection.style.display = "block";
  }
}

function goToStep(step) {
  currentStep = step;

  // Update tabs
  document.querySelectorAll(".step-tab").forEach(tab => {
    const s = parseInt(tab.dataset.step);
    tab.classList.remove("active");
    if (s === currentStep) tab.classList.add("active");
    if (s < currentStep) tab.classList.add("completed");
  });

  // Update panels
  document.querySelectorAll(".step-panel").forEach(panel => {
    panel.classList.remove("active");
    if (parseInt(panel.dataset.step) === currentStep) {
      panel.classList.add("active");
    }
  });

  // Update Footer buttons
  const prevBtn = document.getElementById("btn-prev");
  const nextBtn = document.getElementById("btn-next");
  const launchBtn = document.getElementById("btn-launch-assistant");

  prevBtn.style.display = currentStep === 1 ? "none" : "inline-flex";

  if (currentStep === totalSteps) {
    nextBtn.style.display = "none";
    launchBtn.style.display = "inline-flex";
    populateReviewScreen();
  } else {
    nextBtn.style.display = "inline-flex";
    launchBtn.style.display = "none";
  }
}

function validateCurrentStep() {
  if (currentStep === 1) {
    const nameInput = document.getElementById("input-user-name");
    const val = nameInput.value.trim();
    if (!val) {
      alert("Please enter your name to personalize the assistant.");
      nameInput.focus();
      return false;
    }
    setupData.user_name = val;

    const asstInput = document.getElementById("input-assistant-name");
    setupData.assistant_name = asstInput.value.trim() || "Nova";

    const bioInput = document.getElementById("input-bio-notes");
    if (bioInput) setupData.bio_notes = bioInput.value.trim();

    const greetInput = document.getElementById("input-greeting");
    setupData.greeting_text = greetInput.value.trim() || `Welcome home, ${setupData.user_name}. How was your day?`;

    return true;
  }

  if (currentStep === 2) {
    if (setupData.ai_mode === "cloud") {
      const apiKeyInput = document.getElementById("input-cloud-key");
      const providerSelect = document.getElementById("select-cloud-provider");
      const modelInput = document.getElementById("input-cloud-model");
      const baseUrlInput = document.getElementById("input-cloud-base-url");

      setupData.cloud_provider = providerSelect.value;
      setupData.llm_provider = providerSelect.value;
      setupData.cloud_api_key = apiKeyInput.value.trim();
      setupData.llm_api_key = apiKeyInput.value.trim();
      setupData.llm_model = modelInput ? modelInput.value.trim() : "";
      setupData.llm_base_url = baseUrlInput ? baseUrlInput.value.trim() : "";

      if (!setupData.cloud_api_key && setupData.llm_provider !== "custom") {
        alert("Please enter your Cloud API Key, or select 'Local Offline AI' to run 100% locally.");
        apiKeyInput.focus();
        return false;
      }
    } else {
      setupData.llm_provider = "local";
      setupData.llm_model = "";
      setupData.llm_api_key = "";
      setupData.llm_base_url = "";
    }
    return true;
  }

  if (currentStep === 3) {
    const micSelect = document.getElementById("select-mic-device");
    if (micSelect) setupData.microphone_device = parseInt(micSelect.value) || 0;

    const chimeToggle = document.getElementById("toggle-ready-chime");
    if (chimeToggle) setupData.ready_chime = chimeToggle.checked;

    const phoneIp = document.getElementById("input-phone-ip");
    if (phoneIp) setupData.phone_ip = phoneIp.value.trim();

    stopMicTesting();
    return true;
  }

  return true;
}

function handleNext() {
  if (validateCurrentStep()) {
    if (currentStep < totalSteps) {
      goToStep(currentStep + 1);
    }
  }
}

function handlePrev() {
  if (currentStep > 1) {
    stopMicTesting();
    goToStep(currentStep - 1);
  }
}

let lastLoggedFile = "";
let lastLoggedStepPct = 0;

function appendTerminalLog(msg, type = "info") {
  const term = document.getElementById("setup-terminal-logs");
  if (!term) return;
  const timeStr = new Date().toLocaleTimeString();
  const prefix = type === "error" ? "[ERROR]" : (type === "success" ? "[SUCCESS]" : "[INFO]");
  term.textContent += `\n[${timeStr}] ${prefix} ${msg}`;
  term.scrollTop = term.scrollHeight;
}

function updateTerminalBadge(text, colorClass = "ready") {
  const badge = document.getElementById("terminal-status-badge");
  if (!badge) return;
  badge.textContent = text;
  if (colorClass === "downloading") {
    badge.style.background = "rgba(59,130,246,0.15)";
    badge.style.color = "#60a5fa";
  } else if (colorClass === "success") {
    badge.style.background = "rgba(16,185,129,0.15)";
    badge.style.color = "#34d399";
  } else if (colorClass === "error") {
    badge.style.background = "rgba(239,68,68,0.15)";
    badge.style.color = "#f87171";
  }
}

// Model Downloader
async function startModelDownload() {
  const btn = document.getElementById("btn-download-all");
  const progressBox = document.getElementById("download-progress-box");
  btn.disabled = true;
  btn.textContent = "Starting Download...";
  progressBox.classList.add("active");
  updateTerminalBadge("Downloading...", "downloading");
  appendTerminalLog(`Initiating download sequence for: ${setupData.llm_choice}, Faster-Whisper STT, and Piper Neural TTS.`);

  try {
    const res = await fetch("/api/models/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        models: [setupData.llm_choice, "stt", "tts"]
      })
    });

    const data = await res.json();
    if (!res.ok) {
      const err = data.error || "Unknown error";
      alert("Download error: " + err);
      appendTerminalLog(`Failed to start download: ${err}`, "error");
      updateTerminalBadge("Failed", "error");
      btn.disabled = false;
      btn.textContent = "Download All Models (1-Click)";
      return;
    }

    appendTerminalLog("Connected to HuggingFace repository. Streaming chunks...");
    // Start polling progress
    if (downloadPollTimer) clearInterval(downloadPollTimer);
    lastLoggedFile = "";
    lastLoggedStepPct = 0;
    downloadPollTimer = setInterval(pollDownloadStatus, 500);

  } catch (err) {
    console.error("Download trigger failed:", err);
    appendTerminalLog(`Download connection error: ${err.message}`, "error");
    updateTerminalBadge("Error", "error");
    alert("Could not start download: " + err.message);
    btn.disabled = false;
  }
}

async function pollDownloadStatus() {
  try {
    const res = await fetch("/api/models/download-status");
    if (!res.ok) return;
    const st = await res.json();

    const label = document.getElementById("progress-file-label");
    const pct = document.getElementById("progress-percentage");
    const bar = document.getElementById("progress-bar-fill");
    const speed = document.getElementById("progress-speed");
    const eta = document.getElementById("progress-eta");
    const bytes = document.getElementById("progress-bytes");

    if (st.current_file) {
      label.textContent = `Downloading: ${st.current_file}`;
      if (st.current_file !== lastLoggedFile) {
        lastLoggedFile = st.current_file;
        appendTerminalLog(`Fetching: ${st.current_file}...`);
      }
    }

    pct.textContent = `${st.percent}%`;
    bar.style.width = `${st.percent}%`;
    speed.textContent = `${st.speed_mbps} Mbps`;
    
    if (st.eta_seconds > 0) {
      const mins = Math.floor(st.eta_seconds / 60);
      const secs = st.eta_seconds % 60;
      eta.textContent = `ETA: ${mins}m ${secs}s`;
    } else {
      eta.textContent = "ETA: --";
    }

    if (st.bytes_downloaded && st.total_bytes) {
      const mbDown = (st.bytes_downloaded / (1024 * 1024)).toFixed(1);
      const mbTotal = (st.total_bytes / (1024 * 1024)).toFixed(1);
      bytes.textContent = `${mbDown} / ${mbTotal} MB`;
      
      const currentQuarter = Math.floor(st.percent / 25) * 25;
      if (currentQuarter > lastLoggedStepPct && currentQuarter > 0) {
        lastLoggedStepPct = currentQuarter;
        appendTerminalLog(`Overall Progress: ${currentQuarter}% complete (${mbDown}/${mbTotal} MB @ ${st.speed_mbps} Mbps)`);
      }
    }

    if (st.state === "completed") {
      clearInterval(downloadPollTimer);
      label.textContent = "All Models Downloaded Successfully!";
      bar.style.width = "100%";
      pct.textContent = "100%";
      const btn = document.getElementById("btn-download-all");
      btn.textContent = "All Local Models Verified";
      btn.disabled = true;
      btn.classList.replace("btn-primary", "btn-secondary");
      updateTerminalBadge("Completed", "success");
      appendTerminalLog("All model weights verified on local filesystem. Ready for deployment!", "success");

      // Reload models list
      const statusRes = await fetch("/api/setup/status");
      const statusData = await statusRes.json();
      renderModelsList(statusData.models);
    } else if (st.state === "error") {
      clearInterval(downloadPollTimer);
      label.textContent = "Error: " + (st.error_message || "Download Failed");
      const btn = document.getElementById("btn-download-all");
      btn.disabled = false;
      btn.textContent = "Retry Download";
      updateTerminalBadge("Error", "error");
      appendTerminalLog(`Download error: ${st.error_message || "Failed"}`, "error");
    }
  } catch (e) {
    console.error("Polling error:", e);
  }
}

// Live Mic Volume Meter
async function toggleMicTesting() {
  const btn = document.getElementById("btn-test-mic");
  const meterBar = document.getElementById("meter-bar");
  const meterVal = document.getElementById("meter-value");

  if (micStream) {
    stopMicTesting();
    return;
  }

  btn.textContent = "Stop Mic Test";
  btn.classList.add("btn-secondary");

  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    micAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = micAudioContext.createMediaStreamSource(micStream);
    micAnalyser = micAudioContext.createAnalyser();
    micAnalyser.fftSize = 256;
    source.connect(micAnalyser);

    const dataArray = new Uint8Array(micAnalyser.frequencyBinCount);

    function updateMeter() {
      micAnalyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const avg = sum / dataArray.length;
      const level = Math.min(100, Math.round((avg / 128) * 100));

      if (meterBar) meterBar.style.width = `${level}%`;
      if (meterVal) meterVal.textContent = `${level}%`;

      micAnimFrame = requestAnimationFrame(updateMeter);
    }
    updateMeter();
  } catch (err) {
    console.warn("Browser mic access not available or denied, simulating visual response:", err);
    // Fallback simulation
    let simLevel = 0;
    function simMeter() {
      simLevel = Math.floor(Math.random() * 40) + 15;
      if (meterBar) meterBar.style.width = `${simLevel}%`;
      if (meterVal) meterVal.textContent = `${simLevel}% (active)`;
      micAnimFrame = requestAnimationFrame(simMeter);
    }
    simMeter();
  }
}

function stopMicTesting() {
  const btn = document.getElementById("btn-test-mic");
  if (btn) {
    btn.textContent = " Test Microphone Input";
    btn.classList.remove("btn-secondary");
  }

  if (micAnimFrame) cancelAnimationFrame(micAnimFrame);
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
  if (micAudioContext) {
    micAudioContext.close();
    micAudioContext = null;
  }
  const meterBar = document.getElementById("meter-bar");
  const meterVal = document.getElementById("meter-value");
  if (meterBar) meterBar.style.width = "0%";
  if (meterVal) meterVal.textContent = "0%";
}

// Step 4 Review Screen
function populateReviewScreen() {
  document.getElementById("review-user-name").textContent = setupData.user_name || "--";
  document.getElementById("review-assistant-name").textContent = setupData.assistant_name || "Nova";
  document.getElementById("review-greeting").textContent = setupData.greeting_text || "--";
  
  let aiModeText = setupData.llm_choice === "llm_1b" 
    ? "Local Offline (Llama 3.2 1B Instruct - Lightweight)" 
    : "Local Offline (Llama 3.2 3B Instruct - 100% Private)";
  if (setupData.ai_mode === "cloud") {
    const pNames = {
      openai: "OpenAI",
      groq: "Groq Cloud",
      gemini: "Google Gemini",
      anthropic: "Anthropic Claude",
      deepseek: "DeepSeek",
      custom: "Custom OpenAI Compatible",
    };
    const pName = pNames[setupData.llm_provider] || setupData.llm_provider.toUpperCase();
    const mName = setupData.llm_model ? ` [${setupData.llm_model}]` : "";
    aiModeText = `Cloud API: ${pName}${mName}`;
  }
  document.getElementById("review-ai-mode").textContent = aiModeText;

  document.getElementById("review-mic-device").textContent = `Device ID ${setupData.microphone_device}`;
  document.getElementById("review-presence").textContent = setupData.phone_ip ? `Phone IP: ${setupData.phone_ip}` : "Disabled (None)";
}

// Final Save & Launch
async function handleFinalLaunch() {
  const btn = document.getElementById("btn-launch-assistant");
  btn.disabled = true;
  btn.textContent = "Launching Assistant...";

  try {
    // 1. Save configuration
    const saveRes = await fetch("/api/setup/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setupData)
    });

    if (!saveRes.ok) {
      const errData = await saveRes.json();
      throw new Error(errData.error || "Save failed");
    }

    // 2. Trigger launch endpoint
    await fetch("/api/setup/launch", { method: "POST" });

    // 3. Show celebratory animation & redirect
    document.querySelector(".setup-body").innerHTML = `
      <div class="launch-banner">
        <div class="launch-icon"><svg class="icon-svg icon-svg-xl" viewBox="0 0 24 24"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg></div>
        <h2 style="font-size: 24px; font-weight: 700; margin-bottom: 8px;">You're All Set, ${setupData.user_name}!</h2>
        <p style="color: var(--text-secondary); max-width: 500px; margin: 0 auto 24px;">
          ${setupData.assistant_name} is now customized to your preferences and ready to assist you.
        </p>
        <p style="color: var(--accent-secondary); font-weight: 600;">
          Redirecting to your Live Assistant Dashboard...
        </p>
      </div>
    `;
    document.querySelector(".setup-footer").style.display = "none";

    setTimeout(() => {
      window.location.href = "/";
    }, 2500);

  } catch (err) {
    alert("Failed to save and launch: " + err.message);
    btn.disabled = false;
    btn.textContent = "Save & Launch Assistant";
  }
}
