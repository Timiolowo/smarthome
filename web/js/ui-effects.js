/* ==========================================================================
   UI EFFECTS — Card Spotlight, Sidebar, Topbar Clock, Keyboard Shortcuts
   ========================================================================== */

// Aceternity Card Spotlight Mouse Tracking
function initCardSpotlight() {
  document.querySelectorAll('.card-spotlight').forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--mouse-x', `${x}px`);
      card.style.setProperty('--mouse-y', `${y}px`);
    });
  });
}

// Shadcn Collapsible Sidebar (`collapsible="icon"`)
function toggleSidebar(force) {
  const sidebar = document.getElementById('main-sidebar');
  if (!sidebar) return;

  const isCollapsed = force !== undefined ? force : !sidebar.classList.contains('collapsed');
  if (isCollapsed) {
    sidebar.classList.add('collapsed');
    localStorage.setItem('sidebar-collapsed', 'true');
  } else {
    sidebar.classList.remove('collapsed');
    localStorage.setItem('sidebar-collapsed', 'false');
  }
}
window.toggleSidebar = toggleSidebar;

// Restore sidebar state
if (localStorage.getItem('sidebar-collapsed') === 'true') {
  const sb = document.getElementById('main-sidebar');
  if (sb) sb.classList.add('collapsed');
}

// Topbar Clock
function updateTopbarClock() {
  const now = new Date();
  const hrs = now.getHours().toString().padStart(2, '0');
  const mins = now.getMinutes().toString().padStart(2, '0');
  const clockEl = document.getElementById('topbar-live-clock');
  if (clockEl) clockEl.innerText = `${hrs}:${mins}`;

  const dateEl = document.getElementById('topbar-dynamic-date');
  if (dateEl) {
    const opts = { day: 'numeric', month: 'short', year: 'numeric' };
    dateEl.innerText = `${now.toLocaleDateString('en-US', opts)} • Online`;
  }
}
setInterval(updateTopbarClock, 1000);
updateTopbarClock();

// Keyboard Shortcuts (⌘B for Sidebar)
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'b' || e.key === 'B')) {
    e.preventDefault();
    toggleSidebar();
  }
});
