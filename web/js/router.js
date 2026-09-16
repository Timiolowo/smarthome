/* ==========================================================================
   ROUTER — URL-Based Tab Navigation & History
   ========================================================================== */

// URL path <-> tab ID mapping
const PATH_TO_TAB = {
  '/': 'tab-livedisplay',
  '/voice': 'tab-livedisplay',
  '/home': 'tab-overview',
  '/chat': 'tab-chat',
  '/actions': 'tab-alarms',
  '/alarms': 'tab-alarms',
  '/settings': 'tab-config',
  '/profile': 'tab-user-profile',
  '/ai': 'tab-about-ai',
};
const TAB_TO_PATH = {
  'tab-livedisplay': '/voice',
  'tab-overview': '/home',
  'tab-chat': '/chat',
  'tab-alarms': '/actions',
  'tab-config': '/settings',
  'tab-user-profile': '/profile',
  'tab-about-ai': '/ai',
};

function routeFromURL() {
  const path = window.location.pathname;
  const tabId = PATH_TO_TAB[path] || 'tab-livedisplay';
  const btnMap = {
    'tab-livedisplay': 'nav-btn-livedisplay',
    'tab-overview': 'nav-btn-home',
    'tab-chat': 'nav-btn-chat',
    'tab-alarms': 'nav-btn-actions',
    'tab-config': 'nav-btn-config',
  };
  const btn = document.getElementById(btnMap[tabId] || '');
  showTab(tabId, btn, true);
}
window.routeFromURL = routeFromURL;

window.addEventListener('popstate', () => {
  routeFromURL();
});

function showTab(tabId, el, skipPush, syncWithServer = true) {
  window.scrollTo({ top: 0, behavior: 'instant' });
  window.__currentTabId = tabId;
  document.body.setAttribute('data-tab', tabId);

  // Update browser URL to reflect current tab
  if (!skipPush && TAB_TO_PATH[tabId]) {
    const newPath = TAB_TO_PATH[tabId];
    if (window.location.pathname !== newPath) {
      history.pushState({ tabId }, '', newPath);
    }
  }

  document.querySelectorAll('.section-card').forEach(s => s.classList.remove('visible'));
  const target = document.getElementById(tabId);
  if (target) target.classList.add('visible');

  // If leaving livedisplay, exit kiosk mode to ensure full scrolling
  if (tabId !== 'tab-livedisplay' && document.body.classList.contains('kiosk-mode')) {
    if (typeof toggleKioskMode === 'function') toggleKioskMode(false);
    else document.body.classList.remove('kiosk-mode');
  }

  document.querySelectorAll('.tars-top-nav-btn, .sidebar-menu-btn').forEach(n => n.classList.remove('active'));
  if (el) {
    el.classList.add('active');
  } else {
    const matchingBtn = document.querySelector(`.tars-top-nav-btn[onclick*="${tabId}"], .sidebar-menu-btn[onclick*="${tabId}"]`);
    if (matchingBtn) matchingBtn.classList.add('active');
  }

  const titles = {
    'tab-livedisplay': ['Live Smart Display', 'Ambient StandBy mode, real-time voice HUD, and telemetry stream.'],
    'tab-overview': ['Assistant Overview', 'System status, local models, and smart home controls.'],
    'tab-user-profile': ['Resident Dossier', 'Personal preferences, habits, entertainment tastes, and memories.'],
    'tab-about-ai': ['AI Architecture', 'Identity, behavioral ground rules, privacy guarantees, and hardware.'],
    'tab-alarms': ['Alarms & Timers', 'Live countdowns, cancel controls, and digital sound chime scheduler.'],
    'tab-config': ['Assistant Configuration', 'Preferred resident name, assistant personality, and LLM brain.'],
    'tab-chat': ['Chat Console', 'Direct interaction with your agentic tools, memory, and LLM brain.']
  };

  if (titles[tabId]) {
    const head = document.getElementById('page-heading');
    const sub = document.getElementById('page-subheading');
    const breadcrumbCurrent = document.getElementById('breadcrumb-current-section');
    if (head) head.innerText = titles[tabId][0];
    if (sub) sub.innerText = titles[tabId][1];
    if (breadcrumbCurrent) breadcrumbCurrent.innerText = titles[tabId][0];
  }

  if (typeof resetStandbyIdleTimer === 'function') resetStandbyIdleTimer();

  if (tabId === 'tab-livedisplay') {
    if (typeof updateClock === 'function') updateClock();
    if (typeof pollLiveDisplay === 'function') pollLiveDisplay();
    if (typeof pollLiveEvents === 'function') pollLiveEvents(true);
  } else {
    if (typeof hideIosStandby === 'function') hideIosStandby();
    if (tabId === 'tab-config') {
      if (typeof populateVoiceDropdown === 'function') populateVoiceDropdown();
      if (typeof checkMicPermissionStatus === 'function') checkMicPermissionStatus();
    }
  }

  if (syncWithServer) {
    fetch('/api/ui/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active_tab: tabId })
    }).catch(() => {});
  }
}
window.showTab = showTab;

function setRailActive(el) {
  document.querySelectorAll('.tars-top-nav-btn, .sidebar-menu-btn').forEach(n => n.classList.remove('active'));
  if (el) el.classList.add('active');
}
window.setRailActive = setRailActive;
