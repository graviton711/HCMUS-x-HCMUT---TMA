import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useState,
  type ReactNode,
} from 'react';

export type Locale = 'vi' | 'en';
export type Theme = 'light' | 'dark';

interface Preferences {
  locale: Locale;
  theme: Theme;
  setLocale: (locale: Locale) => void;
  setTheme: (theme: Theme) => void;
  t: (vi: string, en: string) => string;
}

const key = 'di-cung-display-v1';
const PreferencesContext = createContext<Preferences | null>(null);

function readPreferences(): { locale: Locale; theme: Theme } {
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? '{}') as {
      locale?: string;
      theme?: string;
    };
    return {
      locale: saved.locale === 'en' ? 'en' : 'vi',
      theme: saved.theme === 'dark' ? 'dark' : 'light',
    };
  } catch {
    return { locale: 'vi', theme: 'light' };
  }
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [initial] = useState(readPreferences);
  const [locale, setLocale] = useState<Locale>(initial.locale);
  const [theme, setTheme] = useState<Theme>(initial.theme);

  useLayoutEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [locale, theme]);

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify({ locale, theme }));
    } catch {
      /* Preferences still apply for this page. */
    }
  }, [locale, theme]);

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== key) return;
      const next = readPreferences();
      setLocale(next.locale);
      setTheme(next.theme);
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);

  return (
    <PreferencesContext.Provider
      value={{ locale, theme, setLocale, setTheme, t: (vi, en) => (locale === 'vi' ? vi : en) }}
    >
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error('PreferencesProvider is required');
  return value;
}
