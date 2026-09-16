/**
 * ==========================================================================
 * iOS STANDBY AMBIENT DISPLAY CONTROLLER
 * Handles StandBy Mode Clock Ticks, Dynamic Calendar, Smooth RAF Loop & Idle Triggers
 * ==========================================================================
 */
(function () {
  let iosStandbyRafId = null;
  let iosStandbyIdleTimer = null;
  let isIosStandbyActive = false;

  function initIosStandby() {
    generateClockTicks();
    renderStandbyCalendar();
    setupStandbyIdleTracker();
  }

  function generateClockTicks() {
    const ticksGroup = document.getElementById('standby-clock-ticks');
    if (!ticksGroup || ticksGroup.children.length > 0) return;

    const cx = 160;
    const cy = 160;
    const radius = 148;

    for (let i = 0; i < 60; i++) {
      const angle = (i * 6) * (Math.PI / 180);
      const isMajor = i % 5 === 0;
      const tickLen = isMajor ? 12 : 6;
      const rOuter = radius;
      const rInner = radius - tickLen;

      const x1 = cx + rOuter * Math.sin(angle);
      const y1 = cy - rOuter * Math.cos(angle);
      const x2 = cx + rInner * Math.sin(angle);
      const y2 = cy - rInner * Math.cos(angle);

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x1.toFixed(1));
      line.setAttribute('y1', y1.toFixed(1));
      line.setAttribute('x2', x2.toFixed(1));
      line.setAttribute('y2', y2.toFixed(1));
      if (isMajor) line.classList.add('major-tick');
      ticksGroup.appendChild(line);
    }
  }

  function renderStandbyCalendar() {
    const monthEl = document.getElementById('standby-cal-month');
    const yearEl = document.getElementById('standby-cal-year');
    const gridEl = document.getElementById('standby-cal-grid');
    if (!gridEl) return;

    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const today = now.getDate();

    const monthNames = [
      'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
      'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'
    ];

    if (monthEl) monthEl.textContent = monthNames[month];
    if (yearEl) yearEl.textContent = year;

    const firstDayIndex = new Date(year, month, 1).getDay();
    const totalDays = new Date(year, month + 1, 0).getDate();

    let html = '';
    for (let i = 0; i < firstDayIndex; i++) {
      html += '<div class="standby-cal-cell empty"></div>';
    }
    for (let d = 1; d <= totalDays; d++) {
      const isToday = d === today;
      html += `<div class="standby-cal-cell ${isToday ? 'today' : ''}">${d}</div>`;
    }
    gridEl.innerHTML = html;
  }

  function updateAnalogClock() {
    const hourHand = document.getElementById('standby-hour-hand');
    const minHand = document.getElementById('standby-min-hand');
    const secWrap = document.getElementById('standby-sec-hand-wrap');

    if (!hourHand || !minHand || !secWrap) return;

    const now = new Date();
    const ms = now.getMilliseconds();
    const sec = now.getSeconds();
    const min = now.getMinutes();
    const hr = now.getHours() % 12;

    const secAngle = (sec + ms / 1000) * 6;
    const minAngle = (min + sec / 60) * 6;
    const hourAngle = (hr + min / 60 + sec / 3600) * 30;

    hourHand.style.transform = `translateX(-50%) rotate(${hourAngle}deg)`;
    minHand.style.transform = `translateX(-50%) rotate(${minAngle}deg)`;
    secWrap.style.transform = `rotate(${secAngle}deg)`;

    if (isIosStandbyActive) {
      iosStandbyRafId = requestAnimationFrame(updateAnalogClock);
    }
  }

  function showIosStandby() {
    const overlay = document.getElementById('tars-ios-standby');
    if (!overlay) return;

    renderStandbyCalendar();
    generateClockTicks();

    // Update dynamic assistant wake caption
    const captionEl = document.getElementById('standby-status-caption');
    const asstName = (window.cachedStatus?.config?.assistant_name || window.cachedStatus?.assistant?.name || 'Nova').toUpperCase();
    if (captionEl) {
      captionEl.textContent = `WAITING FOR ${asstName} · SAY “HEY ${asstName}” OR CLICK TO WAKE`;
    }

    overlay.style.display = 'flex';
    isIosStandbyActive = true;

    if (iosStandbyRafId) cancelAnimationFrame(iosStandbyRafId);
    iosStandbyRafId = requestAnimationFrame(updateAnalogClock);

    // Notify backend and log transition to terminal
    fetch('/api/system/standby', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'enter' })
    }).catch(() => {});
  }
  window.showIosStandby = showIosStandby;
  window.triggerStandbyMode = showIosStandby;

  function hideIosStandby() {
    const overlay = document.getElementById('tars-ios-standby');
    if (!overlay) return;

    overlay.style.display = 'none';
    const wasActive = isIosStandbyActive;
    isIosStandbyActive = false;

    if (iosStandbyRafId) {
      cancelAnimationFrame(iosStandbyRafId);
      iosStandbyRafId = null;
    }
    resetStandbyIdleTimer();

    if (wasActive) {
      fetch('/api/system/standby', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'exit' })
      }).catch(() => {});
    }
  }
  window.hideIosStandby = hideIosStandby;

  function resetStandbyIdleTimer() {
    if (iosStandbyIdleTimer) {
      clearTimeout(iosStandbyIdleTimer);
      iosStandbyIdleTimer = null;
    }

    const isSpeaking = Boolean(window.__isAssistantSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking));
    const isCapturing = Boolean(window.browserVoiceSession && window.browserVoiceSession.capturing);
    const isProcessing = Boolean(window.browserVoiceSession && window.browserVoiceSession.processing);

    if (isSpeaking || isCapturing || isProcessing) return;

    iosStandbyIdleTimer = setTimeout(() => {
      if (!isIosStandbyActive) {
        showIosStandby();
      }
    }, 45000);
  }
  window.resetStandbyIdleTimer = resetStandbyIdleTimer;

  function setupStandbyIdleTracker() {
    const events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'];
    events.forEach(ev => {
      window.addEventListener(ev, () => {
        if (!isIosStandbyActive) {
          resetStandbyIdleTimer();
        }
      }, { passive: true });
    });
    resetStandbyIdleTimer();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIosStandby);
  } else {
    initIosStandby();
  }
})();
