import { useEffect, useId, useRef, useState } from 'react';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import styles from './chat.module.css';

export function Composer({
  busy,
  canStop = false,
  onSend,
  onStop,
  size = 'regular',
  hint,
}: {
  busy: boolean;
  canStop?: boolean;
  onSend: (text: string) => void;
  onStop?: () => void;
  size?: 'regular' | 'large';
  hint?: [string, string];
}) {
  const { t } = usePreferences();
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wasBusy = useRef(busy);
  const fieldId = useId();
  const ready = value.trim().length > 0 && !busy;

  function submit() {
    if (!ready) return;
    onSend(value.trim());
    setValue('');
    textareaRef.current?.style.removeProperty('height');
    textareaRef.current?.focus();
  }

  useEffect(() => {
    if (wasBusy.current && !busy) textareaRef.current?.focus();
    wasBusy.current = busy;
  }, [busy]);

  const label = t('Nhắn cho TourLens', 'Message TourLens');

  return (
    <div className={`${styles.composer} ${size === 'large' ? styles['composer-large'] : ''}`}>
      <label className="sr-only" htmlFor={fieldId}>
        {label}
      </label>
      <textarea
        ref={textareaRef}
        id={fieldId}
        rows={1}
        value={value}
        disabled={busy}
        onChange={(event) => {
          setValue(event.target.value);
          event.target.style.height = 'auto';
          event.target.style.height = `${Math.min(event.target.scrollHeight, 200)}px`;
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={t(
          'Mô tả chuyến đi bạn muốn… (Enter để gửi)',
          'Describe the trip you want… (Enter to send)',
        )}
      />
      <div className={styles['composer-foot']}>
        <span className={styles['composer-hint']}>
          {t(...(hint ?? ['Mô tả điểm đến, ngày đi, ngân sách', 'Destination, dates and budget']))}
        </span>
        <button
          type="button"
          className={`${styles['composer-submit']} ${canStop ? styles['composer-stop'] : ''}`}
          data-action={canStop ? 'stop' : 'send'}
          aria-label={canStop ? t('Dừng', 'Stop') : t('Gửi', 'Send')}
          title={canStop ? t('Dừng lượt tìm', 'Stop this response') : undefined}
          disabled={canStop ? !onStop : !ready}
          onClick={canStop ? onStop : submit}
        >
          <span className="sr-only">
            {canStop ? t('Dừng lượt tìm', 'Stop response') : t('Tìm tour', 'Find tours')}
          </span>
          <Icon name={canStop ? 'stop' : 'arrow'} size={17} />
        </button>
      </div>
    </div>
  );
}
