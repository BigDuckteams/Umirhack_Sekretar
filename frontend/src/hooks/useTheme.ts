import { useCallback, useEffect, useState } from "react";

export type Theme = "system" | "light" | "dark";
const KEY = "dekanat.theme";
const ORDER: Theme[] = ["system", "light", "dark"];

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* хранилище недоступно */
  }
  return "system";
}

export function useTheme(): { theme: Theme; cycle: () => void; set: (t: Theme) => void } {
  const [theme, setTheme] = useState<Theme>(read);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* не критично */
    }
  }, [theme]);

  const cycle = useCallback(() => setTheme((t) => ORDER[(ORDER.indexOf(t) + 1) % ORDER.length]!), []);
  return { theme, cycle, set: setTheme };
}
