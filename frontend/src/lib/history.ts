import type { TurnResponse } from "../types/api";
import type { SessionStateResponse } from "../types/server";
const times = [
  "20:30",
  "20:32",
  "20:34",
  "20:37",
  "20:39",
  "20:41",
  "20:45",
  "20:47",
  "20:50",
  "20:53",
  "20:55",
  "20:58",
  "21:00",
];
const names = [
  "마지막 손님",
  "남겨둔 책",
  "쓰지 못한 한 문장",
  "문을 닫기 전에",
];
/** 서버 messages가 원문 권한을 가진다. 현재 시각은 항상 state.story_time을 사용한다.
 * 과거 응답을 받은 적 없는 브라우저만 명세의 고정 시각표로 로그 메타데이터를 복원한다.
 * 복원 API에 없는 과거 이미지 URL은 만들어내지 않는다.
 */
export function restoreHistory(
  state: SessionStateResponse,
  cached: TurnResponse[],
): TurnResponse[] {
  return Array.from({ length: state.completed_turns + 1 }, (_, turn) => {
    const saved = cached.find((item) => item.completed_turns === turn);
    const current = turn === state.completed_turns;
    const sceneId = Math.min(4, Math.floor(turn / 3) + 1);
    const knownImage =
      cached.find((item) => item.scene.id === sceneId && item.scene.image_url)
        ?.scene.image_url ?? null;
    return {
      messages: state.messages.filter((message) => message.turn === turn),
      completed_turns: turn,
      story_time: current
        ? state.story_time
        : (saved?.story_time ?? times[turn]),
      scene: {
        id: current ? state.scene.id : sceneId,
        name: current ? state.scene.name : names[sceneId - 1],
        entered: [0, 3, 6, 9].includes(turn),
        image_url: current ? state.scene.image_url : knownImage,
      },
      card_available: current ? state.card_available : false,
      is_final_turn: current ? state.is_final_turn : false,
    };
  });
}
export function appendTurn(
  history: TurnResponse[],
  response: TurnResponse,
): TurnResponse[] {
  return [
    ...history.filter(
      (turn) => turn.completed_turns !== response.completed_turns,
    ),
    response,
  ].sort((a, b) => a.completed_turns - b.completed_turns);
}
