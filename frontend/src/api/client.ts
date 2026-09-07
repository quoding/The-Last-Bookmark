import type { Ending, SessionList, TurnResponse } from "../types/api";
import type {
  SessionDeleteResponse,
  AuthVerifyResponse,
  CardSubmitRequest,
  PortraitRetryResponse,
  PortraitRetryRequest,
  SessionCreateRequest,
  SessionCreateResponse,
  SessionStartResponse,
  SessionStateResponse,
  TurnSubmitRequest,
} from "../types/server";

export const baseURL = import.meta.env.VITE_API_BASE_URL || "mock://local";
export const isMock = baseURL.startsWith("mock:");
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
const errorMessage = (status: number, auth: boolean) =>
  status === 401
    ? auth
      ? "초대 코드를 다시 확인해주세요."
      : "초대 코드를 다시 입력해주세요. 이야기는 저장되어 있어요."
    : status === 429
      ? "시도가 잠시 많았어요. 조금 뒤에 다시 입력해주세요."
      : status === 409
        ? "이야기의 상태가 바뀌었어요. 저장된 기록을 다시 확인해주세요."
        : status === 422
          ? "입력한 내용을 확인해주세요."
          : "연결이 잠시 끊겼어요. 같은 요청으로 다시 시도할 수 있어요.";
export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 45000);
  const token = localStorage.getItem("last-bookmark:token");
  const headers = new Headers(init.headers);
  if (init.body != null) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const options = {
    ...init,
    signal: init.signal ?? controller.signal,
    headers,
  };
  try {
    const response = isMock
      ? await (await import("./mock-server")).mockFetch(path, options)
      : await fetch(`${baseURL.replace(/\/$/, "")}${path}`, options);
    if (response.status === 202 || response.status === 204)
      throw new ApiError(response.status, "마지막 장면을 정리하고 있어요");
    if (!response.ok) {
      const isAuthVerify = path === "/api/auth/verify";
      if (response.status === 401 && !isAuthVerify)
        window.dispatchEvent(new Event("bookmark-auth-expired"));
      let message = errorMessage(response.status, isAuthVerify);
      if (response.status === 403 && isAuthVerify) {
        try {
          const body = (await response.json()) as { detail?: unknown };
          if (typeof body.detail === "string" && body.detail.trim())
            message = body.detail;
        } catch {
          /* detail을 읽을 수 없으면 기존 공통 오류 문구를 사용한다. */
        }
      }
      throw new ApiError(response.status, message);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      navigator.onLine
        ? "응답이 늦어지고 있어요. 같은 요청으로 다시 시도해주세요."
        : "인터넷 연결을 확인해주세요. 작성하던 말은 그대로 있어요.",
    );
  } finally {
    clearTimeout(timeout);
  }
}
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
const sessionPath = (id: string) => `/api/sessions/${encodeURIComponent(id)}`;
export const api = {
  verify: (code: string) =>
    post<AuthVerifyResponse>("/api/auth/verify", { code }),
  sessions: () => request<SessionList>("/api/sessions"),
  deleteSession: (id: string) =>
    request<SessionDeleteResponse>(sessionPath(id), { method: "DELETE" }),
  create: (body: SessionCreateRequest) =>
    post<SessionCreateResponse>("/api/sessions", body),
  portraitRetry: (id: string, body: PortraitRetryRequest) =>
    post<PortraitRetryResponse>(`${sessionPath(id)}/portrait/retry`, body),
  start: (id: string) => post<SessionStartResponse>(`${sessionPath(id)}/start`),
  restore: (id: string) => request<SessionStateResponse>(sessionPath(id)),
  turn: (id: string, body: TurnSubmitRequest) =>
    post<TurnResponse>(`${sessionPath(id)}/turns`, body),
  card: (id: string, body: CardSubmitRequest) =>
    post<TurnResponse>(`${sessionPath(id)}/card`, body),
  end: (id: string, request_id: string) =>
    post<{ status: string }>(`${sessionPath(id)}/end`, { request_id }),
  ending: (id: string) => request<Ending>(`${sessionPath(id)}/ending`),
  retryEndingImage: (id: string) =>
    post<{ image: Ending["image"] }>(`${sessionPath(id)}/ending/image/retry`),
};
export function imageURL(url: string | null): string | null {
  if (!url || isMock || /^(https?:|data:|blob:)/.test(url)) return url;
  return `${baseURL.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}
