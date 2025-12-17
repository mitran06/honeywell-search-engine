export type Theme = "light" | "dark" | "blue-pink" | "custom";

const THEME_KEY = "theme";

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
}

export function loadTheme() {
  const saved = localStorage.getItem(THEME_KEY) as Theme | null;
  const theme = saved || "light";
  document.documentElement.dataset.theme = theme;
}
