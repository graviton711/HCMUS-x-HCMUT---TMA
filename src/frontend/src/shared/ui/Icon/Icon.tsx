import type { ReactNode } from 'react';

export type IconName =
  | 'arrow'
  | 'close'
  | 'search'
  | 'plus'
  | 'chevron'
  | 'pin'
  | 'edit'
  | 'trash'
  | 'check'
  | 'sun'
  | 'moon'
  | 'panel'
  | 'route';

const shapes: Record<IconName, ReactNode> = {
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  search: (
    <>
      <circle cx="10" cy="10" r="6" />
      <path d="m15 15 5 5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  pin: <path d="M8 4h8l-1 6 3 3v2H6v-2l3-3-1-6m4 11v6" />,
  edit: <path d="m15 4 5 5M5 20l5-1L21 8a2 2 0 0 0-5-5L5 14v6Z" />,
  trash: <path d="M4 6h16M9 3h6m-9 3 1 15h10l1-15M10 10v7m4-7v7" />,
  check: <path d="m5 12 4 4L19 6" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M19 5l-1.5 1.5m-11 11L5 19" />
    </>
  ),
  moon: <path d="M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z" />,
  route: (
    <>
      <circle cx="5" cy="5" r="2" />
      <circle cx="19" cy="19" r="2" />
      <path d="M7 5h10a4 4 0 0 1 0 8H7a3 3 0 0 0 0 6h10" />
    </>
  ),
  panel: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9.5 4v16" />
    </>
  ),
};
export function Icon({
  name,
  size = 18,
  className = '',
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {shapes[name]}
    </svg>
  );
}
