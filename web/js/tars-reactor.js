/**
 * ==========================================================================
 * TARS AI VOICE REACTOR & TELEMETRY CONTROLLER
 * Integrates TARS Concentric SVG Reactor, Three.js 3D Particle Orb Toggle,
 * Audio Waveform Canvas, Chronometer, and Location/Weather Display.
 * ==========================================================================
 */

const STATE_COLORS = {
  standby: '#38bdf8',   // Electric Cyan / Light Blue
  listening: '#2563eb', // Deep Tech Blue
  thinking: '#a855f7',  // Neon Purple / Violet
  speaking: '#10b981',  // Emerald Green
  sleep: '#38bdf8',     // Ambient Cyan Sleep
  error: '#ef4444',     // Crimson Red
};

class TarsReactorController {
  constructor() {
    this.currentState = 'standby';
    this.is3DMode = false;
    this.audioContext = null;
    this.analyser = null;
    this.waveformRunning = false;
    this.humor = 75;
    this.honesty = 90;

    // Three.js variables
    this.threeScene = null;
    this.threeCamera = null;
    this.threeRenderer = null;
    this.threeParticles = null;
    this.threeAnimationId = null;

    this.init();
  }

  init() {
    this.initChronometer();
    this.initLocationWeather();
    this.initWaveform();
    this.initControls();
    this.setState('standby');
  }

  /* -------------------------------------------------------------------------- */
  /* 1. CHRONOMETER & TIME                                                      */
  /* -------------------------------------------------------------------------- */
  initChronometer() {
    const updateTime = () => {
      const now = new Date();
      const rawHours = now.getHours();
      const hours12 = String(rawHours % 12 || 12).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      const ampm = rawHours >= 12 ? 'PM' : 'AM';

      const timeEl = document.getElementById('chrono-time');
      const secEl = document.getElementById('chrono-seconds');
      const ampmEl = document.getElementById('chrono-ampm');
      const dateEl = document.getElementById('chrono-date');

      if (timeEl) timeEl.textContent = `${hours12}:${minutes}`;
      if (secEl) secEl.textContent = `:${seconds}`;
      if (ampmEl) ampmEl.textContent = ampm;
      if (dateEl) {
        const options = { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' };
        dateEl.textContent = now.toLocaleDateString('en-US', options).toUpperCase();
      }
      const stripClock = document.getElementById('tars-strip-clock');
      if (stripClock) {
        stripClock.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
      }
    };

    updateTime();
    setInterval(updateTime, 1000);
  }

  /* -------------------------------------------------------------------------- */
  /* 2. LOCATION & WEATHER (Live GeoJS + Open-Meteo Integration)               */
  /* -------------------------------------------------------------------------- */
  async initLocationWeather() {
    const cityEl = document.getElementById('chrono-city');
    const tempEl = document.getElementById('chrono-temp');
    const descEl = document.getElementById('chrono-desc');
    const coordsEl = document.getElementById('chrono-coords');
    const dossierLocEl = document.getElementById('prof-location');

    const updateUI = (city, coords, temp, desc) => {
      if (cityEl) cityEl.textContent = city;
      if (coordsEl) coordsEl.textContent = coords;
      if (tempEl) tempEl.textContent = temp;
      if (descEl) descEl.textContent = desc;
      if (dossierLocEl) dossierLocEl.textContent = city;
    };

    const syncLocationToBackend = async (city, country, lat, lon, temp, desc) => {
      try {
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Africa/Lagos';
        await fetch('/api/location', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            location: city,
            country: country || '',
            latitude: lat,
            longitude: lon,
            timezone: tz,
            weather: { temperature: temp, description: desc }
          })
        });
      } catch (e) {
        console.warn('Backend location sync notice:', e);
      }
    };

    const getWeatherDesc = (code) => {
      if (code === 0) return 'CLEAR';
      if (code === 1 || code === 2) return 'MAINLY CLEAR';
      if (code === 3) return 'PARTLY CLOUDY';
      if (code === 45 || code === 48) return 'FOGGY';
      if (code >= 51 && code <= 55) return 'DRIZZLE';
      if (code >= 56 && code <= 57) return 'FREEZING DRIZZLE';
      if (code >= 61 && code <= 65) return 'RAIN';
      if (code >= 71 && code <= 77) return 'SNOW';
      if (code >= 80 && code <= 82) return 'RAIN SHOWERS';
      if (code >= 85 && code <= 86) return 'SNOW SHOWERS';
      if (code >= 95) return 'THUNDERSTORM';
      return 'OPTIMAL';
    };

    const fetchWeatherForCoords = async (lat, lon, cityName, countryName = '') => {
      const latNum = parseFloat(lat);
      const lonNum = parseFloat(lon);
      const latDir = latNum >= 0 ? '°N' : '°S';
      const lonDir = lonNum >= 0 ? '°E' : '°W';
      const coordStr = `${Math.abs(latNum).toFixed(2)}${latDir}, ${Math.abs(lonNum).toFixed(2)}${lonDir}`;

      try {
        const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${latNum}&longitude=${lonNum}&current_weather=true`);
        if (res.ok) {
          const data = await res.json();
          const temp = `${Math.round(data.current_weather.temperature)}°C`;
          const desc = getWeatherDesc(data.current_weather.weathercode);
          updateUI(cityName, coordStr, temp, desc);
          syncLocationToBackend(cityName, countryName, latNum, lonNum, temp, desc);
          return true;
        }
      } catch (e) {
        console.warn('Open-Meteo fetch failed:', e);
      }
      return false;
    };

    // Primary method: Fast GeoJS IP location
    try {
      const geoRes = await fetch('https://get.geojs.io/v1/ip/geo.json');
      if (geoRes.ok) {
        const geoData = await geoRes.json();
        const city = geoData.city ? `${geoData.city}, ${geoData.country || ''}`.trim() : (geoData.country || 'Current Location');
        const ok = await fetchWeatherForCoords(geoData.latitude, geoData.longitude, city, geoData.country || '');
        if (ok) return;
      }
    } catch (e) {
      console.warn('GeoJS IP lookup error:', e);
    }

    // Secondary fallback: Browser HTML5 geolocation
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          let placeName = 'Local Hub';
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
          await fetchWeatherForCoords(lat, lon, placeName);
        },
        () => {
          updateUI('Nigeria', '6.52°N, 3.37°E', '28°C', 'PARTLY CLOUDY');
          syncLocationToBackend('Nigeria', 'Nigeria', 6.52, 3.37, '28°C', 'PARTLY CLOUDY');
        },
        { timeout: 5000 }
      );
    }
  }

  /* -------------------------------------------------------------------------- */
  /* 3. TARS VOICE STATE MACHINE                                                */
  /* -------------------------------------------------------------------------- */
  setState(newState) {
    this.currentState = newState;
    const accent = STATE_COLORS[newState] || STATE_COLORS.standby;

    // Update CSS custom property for all SVG concentric rings and glowing nodes
    const root = document.querySelector('.tars-center-stage') || document.documentElement;
    root.style.setProperty('--accent', accent);

    const stateLabel = document.getElementById('tars-current-state');
    if (stateLabel) stateLabel.textContent = newState.toUpperCase();

    const stripStateText = document.getElementById('tars-strip-state-text');
    if (stripStateText) stripStateText.textContent = newState.toUpperCase();
    const stripPill = document.getElementById('tars-strip-state-pill');
    if (stripPill) stripPill.style.setProperty('--accent', accent);

    const dialogueText = document.getElementById('tars-dialogue-text');
    if (dialogueText) {
      if (newState === 'standby') {
        const asstName = window.cachedStatus?.config?.assistant_name || 'Nova';
        if (!dialogueText.textContent || dialogueText.textContent.includes('Speaking') || dialogueText.textContent.includes('Processing')) {
          dialogueText.textContent = `"${asstName} is online and standing by. Say \\"Hey ${asstName}\\" or click to talk."`;
        }
      } else if (newState === 'listening') {
        dialogueText.textContent = '"Listening for your voice input..."';
      } else if (newState === 'thinking') {
        dialogueText.textContent = '"Processing reasoning, smart-home nodes, and dialogue..."';
      } else if (newState === 'speaking') {
        if (!dialogueText.textContent || dialogueText.textContent.includes('Processing') || dialogueText.textContent.includes('Listening')) {
          dialogueText.textContent = '"Speaking response..."';
        }
      } else if (newState === 'sleep') {
        dialogueText.textContent = '"Assistant Core is in timed sleep standby."';
      } else if (newState === 'error') {
        dialogueText.textContent = '"Microphone unavailable or voice hardware error."';
      }
    }

    // If 3D is active, update particle color
    if (this.threeParticles && this.threeParticles.material) {
      this.threeParticles.material.color.set(accent);
    }
  }

  cycleState() {
    const states = ['standby', 'listening', 'thinking', 'speaking'];
    const nextIdx = (states.indexOf(this.currentState) + 1) % states.length;
    this.setState(states[nextIdx]);
  }

  /* -------------------------------------------------------------------------- */
  /* 4. AUDIO WAVEFORM VISUALIZER CANVAS                                        */
  /* -------------------------------------------------------------------------- */
  initWaveform() {
    const canvas = document.getElementById('tars-waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const resize = () => {
      canvas.width = canvas.parentElement.clientWidth * window.devicePixelRatio;
      canvas.height = canvas.parentElement.clientHeight * window.devicePixelRatio;
    };
    resize();
    window.addEventListener('resize', resize);

    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;
      const midY = h / 2;

      const accent = STATE_COLORS[this.currentState] || '#38bdf8';
      ctx.lineWidth = 2 * window.devicePixelRatio;

      // Draw dynamic multi-frequency waves
      const bars = 48;
      const barWidth = (w / bars) * 0.55;
      const spacing = w / bars;

      for (let i = 0; i < bars; i++) {
        const x = i * spacing + spacing / 2;
        let amp = 4;

        if (this.currentState === 'listening') {
          amp = Math.sin(phase + i * 0.4) * 14 + Math.cos(phase * 1.5 + i * 0.2) * 10 + 16;
        } else if (this.currentState === 'thinking') {
          amp = Math.sin(phase * 2 + i * 0.6) * 10 + 8;
        } else if (this.currentState === 'speaking') {
          amp = Math.abs(Math.sin(phase * 3 + i * 0.3)) * 20 + Math.random() * 8 + 6;
        } else {
          amp = Math.sin(phase + i * 0.2) * 3 + 4;
        }

        const barH = Math.max(4, amp * window.devicePixelRatio);

        // Gradient bar
        const grad = ctx.createLinearGradient(0, midY - barH, 0, midY + barH);
        grad.addColorStop(0, accent);
        grad.addColorStop(0.5, '#ffffff');
        grad.addColorStop(1, accent);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x - barWidth / 2, midY - barH / 2, barWidth, barH, 4);
        ctx.fill();
      }

      phase += this.currentState === 'speaking' ? 0.08 : 0.04;
      requestAnimationFrame(render);
    };

    render();
  }

  /* -------------------------------------------------------------------------- */
  /* 5. THREE.JS 3D PARTICLE ORB (PersonalAssistant Integration)                */
  /* -------------------------------------------------------------------------- */
  set3DMode(enabled) {
    if (this.is3DMode === enabled) return;
    this.is3DMode = !!enabled;
    const wrapper = document.getElementById('tars-reactor-wrapper');
    const toggleBtn = document.getElementById('tars-mode-toggle');

    if (wrapper) {
      if (this.is3DMode) {
        wrapper.classList.add('is-3d');
        if (toggleBtn) toggleBtn.innerHTML = `
          <svg class="icon-svg" style="width:12px; height:12px;" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/></svg>
          <span id="tars-mode-text">3D ORB</span>
        `;
        this.initThreeScene();
      } else {
        wrapper.classList.remove('is-3d');
        if (toggleBtn) toggleBtn.innerHTML = `
          <svg class="icon-svg" style="width:12px; height:12px;" viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
          <span id="tars-mode-text">2D CORE</span>
        `;
        if (this.threeAnimationId) {
          cancelAnimationFrame(this.threeAnimationId);
          this.threeAnimationId = null;
        }
      }
    }
  }

  toggle3DMode() {
    this.set3DMode(!this.is3DMode);
  }

  initThreeScene() {
    const canvas = document.getElementById('tars-3d-canvas');
    if (!canvas || !window.THREE) return;

    if (this.threeRenderer) {
      this.animateThree();
      return;
    }

    const width = canvas.parentElement.clientWidth;
    const height = canvas.parentElement.clientHeight;

    this.threeScene = new window.THREE.Scene();
    this.threeCamera = new window.THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    this.threeCamera.position.z = 240;

    this.threeRenderer = new window.THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    this.threeRenderer.setSize(width, height);
    this.threeRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Particle Sphere
    const particleCount = 1200;
    const geometry = new window.THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const radius = 75;

    for (let i = 0; i < particleCount; i++) {
      const phi = Math.acos(-1 + (2 * i) / particleCount);
      const theta = Math.sqrt(particleCount * Math.PI) * phi;

      positions[i * 3] = radius * Math.cos(theta) * Math.sin(phi);
      positions[i * 3 + 1] = radius * Math.sin(theta) * Math.sin(phi);
      positions[i * 3 + 2] = radius * Math.cos(phi);
    }

    geometry.setAttribute('position', new window.THREE.BufferAttribute(positions, 3));

    const material = new window.THREE.PointsMaterial({
      color: new window.THREE.Color(STATE_COLORS[this.currentState] || '#38bdf8'),
      size: 2.5,
      transparent: true,
      opacity: 0.85,
      blending: window.THREE.AdditiveBlending,
    });

    this.threeParticles = new window.THREE.Points(geometry, material);
    this.threeScene.add(this.threeParticles);

    this.animateThree();
  }

  animateThree() {
    if (!this.is3DMode) return;

    const speed = this.currentState === 'speaking' ? 0.02 : this.currentState === 'listening' ? 0.015 : 0.006;
    if (this.threeParticles) {
      this.threeParticles.rotation.y += speed;
      this.threeParticles.rotation.x += speed * 0.5;

      // Pulse size with breathing sine wave
      const scale = 1 + Math.sin(Date.now() * 0.003) * 0.06;
      this.threeParticles.scale.set(scale, scale, scale);
    }

    if (this.threeRenderer && this.threeScene && this.threeCamera) {
      this.threeRenderer.render(this.threeScene, this.threeCamera);
    }

    this.threeAnimationId = requestAnimationFrame(() => this.animateThree());
  }

  /* -------------------------------------------------------------------------- */
  /* 6. SYSTEM CONTROLS & DIALS                                                 */
  /* -------------------------------------------------------------------------- */
  initControls() {
    const reactor = document.getElementById('tars-reactor-wrapper');
    if (reactor) {
      reactor.addEventListener('click', () => {
        if (typeof window.toggleLiveVoiceListen === 'function') {
          window.toggleLiveVoiceListen();
        }
      });
    }

    const toggleBtn = document.getElementById('tars-mode-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.toggle3DMode());
    }

    const humorInput = document.getElementById('tars-humor-slider');
    const humorVal = document.getElementById('tars-humor-val');
    if (humorInput && humorVal) {
      humorInput.addEventListener('input', (e) => {
        this.humor = e.target.value;
        humorVal.textContent = `${this.humor}%`;
      });
    }

    const honestyInput = document.getElementById('tars-honesty-slider');
    const honestyVal = document.getElementById('tars-honesty-val');
    if (honestyInput && honestyVal) {
      honestyInput.addEventListener('input', (e) => {
        this.honesty = e.target.value;
        honestyVal.textContent = `${this.honesty}%`;
      });
    }
  }
}

// Global initialization
window.addEventListener('DOMContentLoaded', () => {
  window.tarsController = new TarsReactorController();
});
