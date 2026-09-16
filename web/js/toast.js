/* ==========================================================================
   TOAST — Shadcn Sonner / Toast Notification System
   ========================================================================== */

function showSonner(title, description = '') {
  let container = document.getElementById('sonner-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'sonner-toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'sonner-toast';
  toast.innerHTML = `
    <div style="color:hsl(var(--accent)); flex-shrink:0;">${ICONS.sparkles}</div>
    <div style="display:flex; flex-direction:column; gap:2px; flex:1;">
      <div style="font-weight:600; font-size:0.85rem; color:hsl(var(--foreground));">${title}</div>
      ${description ? `<div style="font-size:0.75rem; color:hsl(var(--muted-foreground));">${description}</div>` : ''}
    </div>
  `;

  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}
window.showSonner = showSonner;
window.showToast = (msg) => showSonner(msg);
