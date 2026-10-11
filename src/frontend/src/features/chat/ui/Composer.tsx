import { useId, useState } from 'react';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import styles from './chat.module.css';

export function Composer({
  busy,
  onSend,
  size = 'regular',
  hint,
}: {
  busy: boolean;
  onSend: (text: string) => void;
  size?: 'regular' | 'large';
  hint?: [string, string];
}) {
  const { t } = usePreferences();
  const [value, setValue] = useState('');
  const fieldId = useId();
  const ready = value.trim().length > 0 && !busy;

  function submit() {
    if (!ready) return;
    onSend(value.trim());
    setValue('');
  }

  const label = t('Nhắn cho TourLens', 'Message TourLens');

  return (
    <div className={`${styles.composer} ${size === 'large' ? styles['composer-large'] : ''}`}>
      <label className="sr-only" htmlFor={fieldId}>
        {label}
      </label>
      <textarea
        id={fieldId}
        rows={size === 'large' ? 4 : 2}
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
          className={`btn btn-primary ${styles['composer-submit']}`}
          aria-label={t('Gửi', 'Send')}
          disabled={!ready}
          onClick={submit}
        >
          <span>{t('Tìm tour', 'Find tours')}</span>
          <Icon name="arrow" size={17} />
        </button>
      </div>
    </div>
  );
}
