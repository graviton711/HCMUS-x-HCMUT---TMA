import { useEffect, useId, useRef, useState } from 'react';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import styles from './PreferencesControl.module.css';

export function PreferencesControl({
  layout = 'row',
  localeMode = 'menu',
}: {
  /** Rail hẹp dùng column; nơi khác dùng row. */
  layout?: 'row' | 'column';
  /** Rail hẹp không đủ chỗ xổ menu nên bấm để đổi thẳng ngôn ngữ. */
  localeMode?: 'menu' | 'cycle';
}) {
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

  const code = locale === 'vi' ? 'VIE' : 'ENG';
  const languageName = locale === 'vi' ? 'Tiếng Việt' : 'English';

  return (
    <div className={styles.root} data-layout={layout} ref={root}>
      <div className={styles['language-picker']}>
        {localeMode === 'cycle' ? (
          <button
            type="button"
            className={styles['locale-cycle']}
            aria-label={t(
              `Ngôn ngữ: ${languageName}. Bấm để đổi ngôn ngữ.`,
              `Language: ${languageName}. Activate to switch language.`,
            )}
            title={t('Đổi ngôn ngữ', 'Switch language')}
            onClick={() => setLocale(locale === 'vi' ? 'en' : 'vi')}
          >
            <span aria-hidden="true">{locale === 'vi' ? 'VI' : 'EN'}</span>
          </button>
        ) : (
          <>
            <button
              ref={trigger}
              type="button"
              className={styles['preferences-trigger']}
              aria-expanded={open}
              aria-controls={optionsId}
              aria-label={t('Chọn ngôn ngữ', 'Choose language')}
              title={t('Chọn ngôn ngữ', 'Choose language')}
              onClick={() => setOpen(!open)}
            >
              <span aria-hidden="true">{code}</span>
              <Icon name="chevron" size={13} />
            </button>
            {open && (
              <div
                className={styles['preferences-panel']}
                id={optionsId}
                role="group"
                aria-label={t('Ngôn ngữ', 'Language')}
              >
                <h2>{t('Ngôn ngữ', 'Language')}</h2>
                <div className={styles['preferences-choices']}>
                  {(
                    [
                      ['vi', 'VIE', 'Tiếng Việt'],
                      ['en', 'ENG', 'English'],
                    ] as const
                  ).map(([value, itemCode, label]) => (
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
                      <span className={styles['language-code']} aria-hidden="true">
                        {itemCode}
                      </span>
                      <span>{label}</span>
                      {locale === value && <Icon name="check" size={15} />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
      <button
        type="button"
        className={styles['theme-toggle']}
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
        <Icon name={theme === 'light' ? 'sun' : 'moon'} size={17} />
      </button>
    </div>
  );
}
