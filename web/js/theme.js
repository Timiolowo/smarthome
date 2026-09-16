/* ==========================================================================
   THEME — Dark Mode & Light Mode Engine
   ========================================================================== */

function setTheme(mode) {
  const btnDark = document.getElementById('btn-dark');
  const btnLight = document.getElementById('btn-light');

  if (mode === 'light') {
    document.documentElement.classList.remove('dark');
    if (btnLight) btnLight.classList.add('active');
    if (btnDark) btnDark.classList.remove('active');
    localStorage.setItem('smarthome_theme', 'light');
  } else {
    document.documentElement.classList.add('dark');
    if (btnDark) btnDark.classList.add('active');
    if (btnLight) btnLight.classList.remove('active');
    localStorage.setItem('smarthome_theme', 'dark');
  }
}
window.setTheme = setTheme;
window.toggleTheme = function() {
  const isDark = document.documentElement.classList.contains('dark');
  setTheme(isDark ? 'light' : 'dark');
};

const savedTheme = localStorage.getItem('smarthome_theme');
if (savedTheme === 'light') {
  setTheme('light');
} else {
  setTheme('dark');
}
