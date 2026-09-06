import type { CSSProperties } from 'react';
export function Icon({ name, size = 20, style }: { name: 'book' | 'arrow' | 'back' | 'dice' | 'menu' | 'close' | 'bookmark' | 'check' | 'chevron'; size?: number; style?: CSSProperties }) {
  const paths = {
    book: <><path d="M12 5C8 2 4 3 2 4v15c3-1 6-1 10 2 4-3 7-3 10-2V4c-2-1-6-2-10 1Z"/><path d="M12 5v16"/></>,
    arrow: <><path d="M4 12h15m-6-6 6 6-6 6"/></>, back: <path d="M20 12H5m6-6-6 6 6 6"/>,
    dice: <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 7h.01M17 7h.01M12 12h.01M7 17h.01M17 17h.01" strokeWidth="3"/></>,
    menu: <path d="M5 7h14M5 12h14M5 17h14"/>, close: <path d="m6 6 12 12M18 6 6 18"/>,
    bookmark: <path d="M6 3h12v18l-6-4-6 4V3Z"/>, check: <path d="m5 12 4 4L19 6"/>, chevron: <path d="m9 5 7 7-7 7"/>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" style={style}>{paths[name]}</svg>;
}
