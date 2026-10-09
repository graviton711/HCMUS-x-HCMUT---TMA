import type { ReactNode } from 'react';
const shapes: Record<string, ReactNode> = {
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  menu: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </>
  ),
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
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6m0-10v.2" />
    </>
  ),
  source: <path d="M14 4h6v6m0-6-9 9M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" />,
  leaf: <path d="M20 3c0 11-4 16-10 16-4 0-6-3-6-6C4 7 10 5 20 3ZM4 21l10-10" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M19 5l-1.5 1.5m-11 11L5 19" />
    </>
  ),
  moon: <path d="M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z" />,
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21v-2a8 8 0 0 1 16 0v2" />
    </>
  ),
  logout: <path d="M10 4H4v16h6m3-12 4 4-4 4m-5-4h13" />,
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 6 9 7 9-7" />
    </>
  ),
  route: (
    <>
      <circle cx="5" cy="5" r="2" />
      <circle cx="19" cy="19" r="2" />
      <path d="M7 5h10a4 4 0 0 1 0 8H7a3 3 0 0 0 0 6h10" />
    </>
  ),
  left: <path d="M20 12H5m6-6-6 6 6 6" />,
  history: (
    <>
      <path d="M3 11a9 9 0 1 1 3 7M3 4v7h7m2-4v5l3 2" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  download: <path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5" />,
  warning: (
    <>
      <path d="m12 3 10 18H2L12 3Z" />
      <path d="M12 9v5m0 3v.1" />
    </>
  ),
  more: (
    <>
      <circle cx="5" cy="12" r="1" />
      <circle cx="12" cy="12" r="1" />
      <circle cx="19" cy="12" r="1" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 6h8m4 0h4M4 12h3m4 0h9M4 18h10m4 0h2" />
      <circle cx="14" cy="6" r="2" />
      <circle cx="9" cy="12" r="2" />
      <circle cx="16" cy="18" r="2" />
    </>
  ),
};
export function Icon({
  name,
  size = 18,
  className = '',
}: {
  name: string;
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
      {shapes[name] ?? shapes.info}
    </svg>
  );
}
