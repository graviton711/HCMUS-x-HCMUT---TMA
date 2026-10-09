import {
  createContext,
  useContext,
  useEffect,
  useId,
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
  const optionsId = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        trigger.current?.focus();
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
    <div className="preferences">
      <div className="language-picker" ref={root}>
        <button
          ref={trigger}
          type="button"
          className="preferences-trigger"
          aria-expanded={open}
          aria-controls={optionsId}
          aria-label={t('Chọn ngôn ngữ', 'Choose language')}
          title={t('Chọn ngôn ngữ', 'Choose language')}
          onClick={() => setOpen(!open)}
        >
          <span>{locale === 'vi' ? 'VIE' : 'ENG'}</span>
          <Icon name="chevron" size={14} />
        </button>
        {open && (
          <div className="preferences-panel" id={optionsId}>
            <h2>{t('Ngôn ngữ', 'Language')}</h2>
            <div
              className="preferences-choices"
              role="group"
              aria-label={t('Ngôn ngữ', 'Language')}
            >
              {(
                [
                  ['vi', 'VIE', 'Tiếng Việt'],
                  ['en', 'ENG', 'English'],
                ] as const
              ).map(([value, code, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-label={label}
                  aria-pressed={locale === value}
                  onClick={() => {
                    setLocale(value);
                    setOpen(false);
                    trigger.current?.focus();
                  }}
                >
                  <span className="language-code" aria-hidden="true">
                    {code}
                  </span>
                  <span>{label}</span>
                  {locale === value && <Icon name="check" size={16} />}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
      <button
        type="button"
        className="theme-toggle"
        aria-label={
          theme === 'light'
            ? t('Chuyển sang giao diện tối', 'Switch to dark mode')
            : t('Chuyển sang giao diện sáng', 'Switch to light mode')
        }
        title={
          theme === 'light'
            ? t('Chuyển sang giao diện tối', 'Switch to dark mode')
            : t('Chuyển sang giao diện sáng', 'Switch to light mode')
        }
        onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
      >
        <Icon name={theme === 'light' ? 'sun' : 'moon'} size={19} />
      </button>
    </div>
  );
}
