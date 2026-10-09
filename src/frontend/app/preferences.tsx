import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Icon } from '../components/Icon';

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

export function PreferencesControl() {
  const { locale, theme, setLocale, setTheme, t } = usePreferences();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        root.current?.querySelector<HTMLButtonElement>('.preferences-trigger')?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);
  return (
    <div className="preferences" ref={root}>
      <button
        className="preferences-trigger"
        aria-expanded={open}
        aria-controls="display-preferences"
        aria-label={t('Tùy chọn hiển thị', 'Display preferences')}
        onClick={() => setOpen(!open)}
      >
        <span>{locale === 'vi' ? 'VIE' : 'ENG'}</span>
        <Icon name={theme === 'light' ? 'sun' : 'moon'} size={17} />
        <Icon name="chevron" size={14} />
      </button>
      {open && (
        <div className="preferences-panel" id="display-preferences">
          <h2>{t('Hiển thị', 'Display')}</h2>
          <fieldset>
            <legend>{t('Ngôn ngữ', 'Language')}</legend>
            <div className="preferences-choices">
              <button aria-pressed={locale === 'vi'} onClick={() => setLocale('vi')}>
                Tiếng Việt
              </button>
              <button aria-pressed={locale === 'en'} onClick={() => setLocale('en')}>
                English
              </button>
            </div>
          </fieldset>
          <fieldset>
            <legend>{t('Giao diện', 'Appearance')}</legend>
            <div className="preferences-choices">
              <button aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>
                <Icon name="sun" />
                {t('Sáng', 'Light')}
              </button>
              <button aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>
                <Icon name="moon" />
                {t('Tối', 'Dark')}
              </button>
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );
}
