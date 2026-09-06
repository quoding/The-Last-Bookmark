import type { Ending, SessionList } from '../types/api';
import { mockEnding, mockSessions } from './mock';

// mock://local을 API 원점(예: https://example.com)으로 바꾸면 fetch를 사용한다.
export const baseURL = import.meta.env.VITE_API_BASE_URL || 'mock://local';
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; }
}
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (baseURL.startsWith('mock:')) {
    await new Promise(resolve => setTimeout(resolve, 350));
    if (path === '/api/sessions') return structuredClone(mockSessions) as T;
    if (/\/ending$/.test(path)) return structuredClone(mockEnding) as T;
    throw new ApiError(404, '아직 연결되지 않은 요청이에요.');
  }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(`${baseURL.replace(/\/$/, '')}${path}`, {
      ...init, signal: init.signal ?? controller.signal,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    });
    if (!response.ok) throw new ApiError(response.status, response.status === 429 ? '잠시 후 다시 시도해주세요.' : '연결이 잠시 끊겼어요. 다시 시도해주세요.');
    return await response.json() as T;
  } finally { clearTimeout(timeout); }
}
export const api = {
  sessions: () => request<SessionList>('/api/sessions'),
  ending: (id: string) => request<Ending>(`/api/sessions/${encodeURIComponent(id)}/ending`),
};
