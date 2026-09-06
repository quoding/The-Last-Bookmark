import type { TurnResponse } from '../types/api';
export const HINTS: Record<number, string[]> = {
  1: ['뭐부터 도와주면 돼요?', '마지막 인사는 하고 싶어서요.', '오늘은 다른 얘기 해도 돼요?'],
  2: ['어떤 책인지 궁금해요.', '책갈피에 얽힌 이야기가 있어요?', '문을 닫고 나면 조금 쉬실 수 있어요?'],
  3: ['거창하지 않아도 괜찮아요.', '어떤 말을 남기고 싶었어요?', '조금 더 생각해도 괜찮아요.'],
  4: ['비가 잦아들 때까지 같이 있을게요.', '책을 다 읽으면 감상 보내도 될까요?', '오늘까지 이곳을 지켜줘서 고마워요.'],
};
export const graphemes = (text: string) => Array.from(new Intl.Segmenter('ko', { granularity: 'grapheme' }).segment(text), item => item.segment);
export const limitCard = (text: string) => graphemes(text).slice(0, 80).join('');
export const timeProgress = (time: string) => {
  const [hour, minute] = time.split(':').map(Number);
  return Math.max(0, Math.min(100, ((hour * 60 + minute - 1230) / 30) * 100));
};
/** entered 응답은 마지막 narration만 다음 장면 진입 서술로 렌더한다. */
export function splitTransition(turn: TurnResponse) {
  const last = turn.messages.at(-1);
  const entry = turn.scene.entered && turn.completed_turns > 0 && last?.kind === 'narration' ? last : undefined;
  return { reaction: entry ? turn.messages.slice(0, -1) : turn.messages, entry };
}
