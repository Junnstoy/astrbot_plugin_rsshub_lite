let isDarkMode = false;
let themeChangeListeners = [];

export function initTheme() {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  isDarkMode = mediaQuery.matches;
  mediaQuery.addEventListener('change', (e) => {
    setDarkMode(e.matches);
  });
  applyTheme();
  return isDarkMode;
}

export function setDarkMode(dark) {
  if (isDarkMode === dark) return;
  isDarkMode = dark;
  applyTheme();
  themeChangeListeners.forEach((l) => l(isDarkMode));
}

function applyTheme() {
  document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
  document.body.classList.toggle('dark-mode', isDarkMode);
}

export function isDarkTheme() {
  return isDarkMode;
}

export function onThemeChange(listener) {
  themeChangeListeners.push(listener);
}

export function offThemeChange(listener) {
  themeChangeListeners = themeChangeListeners.filter((l) => l !== listener);
}
