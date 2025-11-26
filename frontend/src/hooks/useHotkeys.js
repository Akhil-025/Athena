import { useEffect } from "react";
export default function useHotkeys(map = {}) {
  useEffect(() => {
    const handler = (e) => {
      const key = `${e.ctrlKey ? "ctrl." : ""}${e.key.toLowerCase()}`;
      if(map[key]) {
        e.preventDefault();
        map[key](e);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [map]);
}
