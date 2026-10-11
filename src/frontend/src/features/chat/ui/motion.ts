/* Motion only exists to carry a state change; keep it short and calm. */

export const EASE = [0.2, 0.7, 0.3, 1] as const;

export const rise = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.18, ease: EASE },
};

export const staggerParent = {
  animate: { transition: { staggerChildren: 0.03 } },
};

export const collapse = {
  initial: { height: 0, opacity: 0 },
  animate: { height: 'auto', opacity: 1 },
  exit: { height: 0, opacity: 0 },
  transition: { duration: 0.2, ease: EASE },
};
