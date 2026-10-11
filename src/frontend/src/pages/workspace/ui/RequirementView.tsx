import type { CurrentRequirement } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { conditionText, fieldLabel } from '../../../features/chat';

export function RequirementView({ requirement }: { requirement: CurrentRequirement }) {
  const { t } = usePreferences();
  return (
    <section className="current-card" aria-labelledby="interpreted-title">
      <h2 id="interpreted-title">{t('Backend đã hiểu', 'Interpreted by the backend')}</h2>
      {requirement.missing.length > 0 && (
        <p className="current-missing">
          {t('Thiếu dữ kiện bắt buộc:', 'Missing required information:')}{' '}
          {requirement.missing.join(', ')}
        </p>
      )}
      {requirement.conditions.length ? (
        <ul className="current-condition-list">
          {requirement.conditions.map((condition) => (
            <li key={condition.id}>
              <span>{fieldLabel(condition.field, t)}</span>
              <code>
                {conditionText(condition.operator, condition.value, t)}
              </code>
              <small>{condition.strength}</small>
            </li>
          ))}
        </ul>
      ) : (
        <p>
          {t(
            'Chưa trích xuất được điều kiện. Có thể tiếp tục để xem dữ kiện nào còn thiếu.',
            'No criteria were extracted. You can continue to see what data is missing.',
          )}
        </p>
      )}
    </section>
  );
}
