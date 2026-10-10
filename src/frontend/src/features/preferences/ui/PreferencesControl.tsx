import { useEffect, useId, useRef, useState } from 'react';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import styles from './PreferencesControl.module.css';

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
    <div className={styles.root}>
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
