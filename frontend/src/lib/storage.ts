/** 화면 복원 캐시. API 응답이 아닌 브라우저 로컬 상태다. */
export function readLocal<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(`last-bookmark:${key}`); return raw ? JSON.parse(raw) as T : fallback; } catch { return fallback; }
}
export function saveLocal(key: string, value: unknown) { localStorage.setItem(`last-bookmark:${key}`, JSON.stringify(value)); }
export function removeLocal(key: string) { localStorage.removeItem(`last-bookmark:${key}`); }
export const scopedKey = (token: string, key: string) => `${token}:${key}`;
