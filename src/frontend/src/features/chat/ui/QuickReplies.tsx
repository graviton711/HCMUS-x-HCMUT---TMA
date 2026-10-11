import { motion } from 'framer-motion';
import { rise } from './motion';
import styles from './chat.module.css';

export function QuickReplies({
  options,
  onPick,
  disabled,
}: {
  options: { label: string; value: string }[];
  onPick: (value: string) => void;
  disabled?: boolean;
}) {
  if (!options.length) return null;
  return (
    <motion.div {...rise} className={styles['slot-options']}>
      {options.map((option) => (
        <motion.button
          key={option.value}
          type="button"
          disabled={disabled}
          onClick={() => onPick(option.value)}
          whileTap={{ scale: 0.98 }}
          className="chip chip-button"
        >
          {option.label}
        </motion.button>
      ))}
    </motion.div>
  );
}
