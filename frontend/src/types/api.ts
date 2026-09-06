/** CLAUDE.md 6.1. 응답 필드는 계약에 명시된 것만 사용한다. */
export type Message = {
  id: string;
  turn: number;
  text: string;
} & ({ kind: 'player' | 'reply' | 'narration' } | { kind: 'record'; record_type: 'promise' | 'fact' | 'memory' });

export interface Session {
  id: string;
  index: number;
  status: 'completed' | 'in_progress' | 'ended_early';
  completed_turns: number;
  ending_title: string | null;
  portrait_url: string | null;
  created_at: string;
}
export interface SessionList { sessions: Session[] }
export interface TurnResponse {
  messages: Message[];
  completed_turns: number;
  story_time: string;
  scene: { id: number; name: string; entered: boolean; image_url: string | null };
  card_available: boolean;
  is_final_turn: boolean;
}
export interface Ending {
  title: string;
  body: string;
  card: { written: boolean; text: string | null; author: 'player' | 'seoyun' | null };
  evidence: { message_id: string; turn: number; story_time: string; scene_name: string; quote: string; effect: string }[];
  unresolved: string[];
  image: { status: 'generating' | 'done' | 'failed' | 'refused'; url: string | null };
}
