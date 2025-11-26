import React, { useEffect } from "react";

export default function ThemeToggle({ theme, setTheme }) {
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [theme]);

  return (
    <button onClick={() => setTheme(t => t === "dark" ? "light" : "dark")} className="px-3 py-2 rounded bg-white/5">
      { theme === "dark" ? "🌙" : "☀️" }
    </button>
  );
}
