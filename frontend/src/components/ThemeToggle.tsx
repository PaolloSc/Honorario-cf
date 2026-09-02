"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

type Theme = "light" | "dark";

function applyTheme(theme: Theme | null) {
  if (theme) document.documentElement.setAttribute("data-theme", theme);
  else document.documentElement.removeAttribute("data-theme");
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// Sem preferência salva, mostra o estado do sistema (ver script inline no layout,
// que já aplicou isso antes do primeiro paint) — clicar grava uma escolha explícita.
export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    setDark(saved ? saved === "dark" : systemPrefersDark());
  }, []);

  const toggle = () => {
    const next: Theme = dark ? "light" : "dark";
    setDark(!dark);
    localStorage.setItem("theme", next);
    applyTheme(next);
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label={dark ? "Mudar para modo claro" : "Mudar para modo escuro"}
      onClick={toggle}
      className={`relative w-[52px] h-[26px] rounded-full shrink-0 transition-colors ${
        dark ? "bg-primary" : "bg-primary-dark"
      }`}
    >
      <svg className="absolute left-[6px] top-[6px]" width="12" height="12" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="4" stroke="#FAF8F5" strokeWidth="2" />
        <path
          d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
          stroke="#FAF8F5"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      <svg className="absolute right-[6px] top-[6.5px]" width="11" height="11" viewBox="0 0 24 24" fill="none">
        <path d="M21 12.6A9 9 0 1 1 11.4 3a7 7 0 0 0 9.6 9.6Z" stroke="#FAF8F5" strokeWidth="2" strokeLinejoin="round" />
      </svg>
      <motion.span
        className="absolute top-[3px] w-5 h-5 rounded-full bg-white shadow-sm flex items-center justify-center overflow-hidden"
        animate={{ x: dark ? 29 : 3 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      >
        <AnimatePresence mode="wait" initial={false}>
          {dark ? (
            <motion.svg
              key="moon"
              width="11" height="11" viewBox="0 0 24 24" fill="none"
              initial={{ opacity: 0, rotate: -90, scale: 0.5 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: 90, scale: 0.5 }}
              transition={{ duration: 0.2 }}
            >
              <path d="M21 12.6A9 9 0 1 1 11.4 3a7 7 0 0 0 9.6 9.6Z" stroke="#3FCB98" strokeWidth="2" strokeLinejoin="round" />
            </motion.svg>
          ) : (
            <motion.svg
              key="sun"
              width="12" height="12" viewBox="0 0 24 24" fill="none"
              initial={{ opacity: 0, rotate: 90, scale: 0.5 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: -90, scale: 0.5 }}
              transition={{ duration: 0.2 }}
            >
              <circle cx="12" cy="12" r="4" stroke="#B45309" strokeWidth="2" />
              <path
                d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
                stroke="#B45309"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </motion.svg>
          )}
        </AnimatePresence>
      </motion.span>
    </button>
  );
}
