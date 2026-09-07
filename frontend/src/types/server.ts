/** 기존 backend/app/schemas.py에 정의된 보조 계약. 새 응답 필드를 설계하지 않는다. */
import type { Message, TurnResponse } from "./api";
import type { Appearance } from "../lib/presets";
export interface AuthVerifyResponse {
  token: string;
}
export interface PortraitStatus {
  status: "pending" | "done" | "failed" | "refused";
  url: string | null;
  retry_count: number;
  retry_limit: number;
}
export interface SessionCreateResponse {
  id: string;
  index: number;
  portrait: PortraitStatus;
}
export interface PortraitRetryResponse {
  portrait: PortraitStatus;
}
export interface SessionStartResponse {
  id: string;
  completed_turns: number;
  story_time: string;
  scene: TurnResponse["scene"];
}
export interface SceneImageEntry {
  id: number;
  name: string;
  image_url: string | null;
}
export interface SessionStateResponse {
  id: string;
  status: string;
  completed_turns: number;
  story_time: string;
  scene: TurnResponse["scene"];
  messages: Message[];
  card_available: boolean;
  is_final_turn: boolean;
  portrait: PortraitStatus;
  portrait_confirmed: boolean;
  presets: Appearance;
  scenes: SceneImageEntry[];
}
export interface SessionCreateRequest {
  request_id: string;
  presets: Appearance;
}
export interface PortraitRetryRequest {
  request_id: string;
}
export interface TurnSubmitRequest {
  request_id: string;
  text: string;
}
export interface CardSubmitRequest {
  request_id: string;
  action: "write" | "leave_blank";
  text: string | null;
}
