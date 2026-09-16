/* ==========================================================================
   SMART HOME — Device Controls, Media Playback & Security
   ========================================================================== */

function scrollToRoom(roomId, el) {
  showTab('tab-overview', el);
  setRailActive(el);
  const target = document.getElementById(roomId);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.style.borderColor = 'var(--lg-teal)';
    setTimeout(() => target.style.borderColor = '', 1600);
  }
}
window.scrollToRoom = scrollToRoom;

function toggleLiquidSwitch(el, deviceName) {
  const isChecked = el.getAttribute('aria-checked') === 'true';
  const newState = !isChecked;
  el.setAttribute('aria-checked', newState ? 'true' : 'false');
  showSonner(deviceName, newState ? 'Switched ON' : 'Switched OFF');
}
window.toggleLiquidSwitch = toggleLiquidSwitch;

function setDimmerStep(step) {
  const dots = document.querySelectorAll('#living-dimmer-track .dimmer-dot');
  dots.forEach((dot, index) => {
    if (index < step) {
      dot.classList.add('active');
    } else {
      dot.classList.remove('active');
    }
  });
  const pct = Math.round((step / dots.length) * 100);
  const valEl = document.getElementById('living-dimmer-val');
  if (valEl) valEl.innerText = `${pct}%`;
  showSonner('Living Room Lighting', `Brightness set to ${pct}%`);
}
window.setDimmerStep = setDimmerStep;

let isPlaying = true;
function toggleMediaPlayback() {
  isPlaying = !isPlaying;
  const playIcon = document.getElementById('icon-media-play');
  const pauseIcon = document.getElementById('icon-media-pause');
  if (isPlaying) {
    if (playIcon) playIcon.style.display = 'none';
    if (pauseIcon) pauseIcon.style.display = 'block';
    showSonner('Media Playback', 'Resumed: I Took A Ride');
  } else {
    if (playIcon) playIcon.style.display = 'block';
    if (pauseIcon) pauseIcon.style.display = 'none';
    showSonner('Media Playback', 'Paused');
  }
}
window.toggleMediaPlayback = toggleMediaPlayback;

function prevMediaTrack() {
  showSonner('Media Player', 'Previous Track: Over The Moon');
  const title = document.getElementById('media-track-name');
  const sub = document.getElementById('media-track-sub');
  if (title) title.innerText = 'Over The Moon';
  if (sub) sub.innerText = 'The Marías';
}
window.prevMediaTrack = prevMediaTrack;

function nextMediaTrack() {
  showSonner('Media Player', 'Next Track: Sunset Rollercoaster');
  const title = document.getElementById('media-track-name');
  const sub = document.getElementById('media-track-sub');
  if (title) title.innerText = 'Vanilla';
  if (sub) sub.innerText = 'Sunset Rollercoaster';
}
window.nextMediaTrack = nextMediaTrack;

let isLocked = false;
function toggleSmartLock() {
  isLocked = !isLocked;
  const icon = document.getElementById('dock-lock-icon');
  const status = document.getElementById('dock-lock-status-text');
  if (isLocked) {
    if (icon) {
      icon.innerHTML = '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>';
      icon.style.color = 'var(--lg-amber)';
    }
    if (status) status.innerText = 'Locked';
    showSonner('Security Lock', 'Main door is now Locked');
  } else {
    if (icon) {
      icon.innerHTML = '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>';
      icon.style.color = 'var(--lg-teal)';
    }
    if (status) status.innerText = 'Unlocked';
    showSonner('Security Lock', 'Main door is now Unlocked');
  }
}
window.toggleSmartLock = toggleSmartLock;
