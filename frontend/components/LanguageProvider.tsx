"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

export type UiLang = "en" | "ko";

type LanguageContextValue = {
  lang: UiLang;
  setLang: (l: UiLang) => void;
  /**
   * Helper: returns the Korean name when lang === 'ko' AND a translation
   * exists, otherwise falls back to the English name. Keeps individual
   * components from sprinkling `lang === 'ko' && set.name_ko ? ... : ...`
   * everywhere.
   */
  setName: (s: { name: string; name_ko?: string | null }) => string;
};

const STORAGE_KEY = "pulllist_lang";

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  // Default 'en' on first render so the server-rendered HTML matches the
  // hydrated client. We swap to the persisted preference inside the
  // effect below; one flicker on first paint for KR users is acceptable
  // for v1, full SSR-aware i18n is a bigger refactor.
  const [lang, setLangState] = useState<UiLang>("en");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "ko" || stored === "en") setLangState(stored);
    } catch {
      // localStorage may be blocked (private mode); stay on default.
    }
  }, []);

  const setLang = useCallback((l: UiLang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // ignore
    }
  }, []);

  const setName = useCallback(
    (s: { name: string; name_ko?: string | null }) =>
      lang === "ko" && s.name_ko ? s.name_ko : s.name,
    [lang],
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, setName }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return ctx;
}
