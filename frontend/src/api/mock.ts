import type { Ending, Message, SessionList, TurnResponse } from "../types/api";

// 목 서버의 시계. 실제 UI는 TurnResponse.story_time을 그대로 표시한다.
export const TIMES = [
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
export const SCENE_NAMES = [
  "마지막 손님",
  "남겨둔 책",
  "쓰지 못한 한 문장",
  "문을 닫기 전에",
];
export const SCENE_ENTRIES = [
  "상자 사이로 작은 통로가 남아 있다. 서윤이 비어 있는 상자를 발끝으로 밀어둔다.",
  "카운터의 스탠드 아래, 《조금 늦은 안부》가 놓인다. 책 사이로 끝이 해진 파란 천 책갈피가 보인다.",
  "창가 탁자에 작은 카드와 은색 펜이 놓인다. 빗물이 유리를 따라 천천히 흘러내린다.",
  "서윤이 남은 조명을 끄고 열쇠를 챙긴다. 문 밖 처마 아래에서는 빗소리가 조금 더 선명하다.",
];
export const INPUTS = [
  "마지막 인사는 하고 싶어서요. 정리도 조금 도울게요.",
  "테이프 끝은 접어둘게요. 다음에 쓰기 편하게.",
  "문을 닫고 나면, 조금 쉬실 수 있어요?",
  "저한테 추천하려고 남겨두신 거예요?",
  "책갈피, 계속 쓰고 있어요.",
  "이 책은 고맙게 받을게요. 천천히 읽고 싶어요.",
  "거창하지 않아도 괜찮아요. 오늘처럼만 적어도.",
  "좋은 이야기는 주소가 바뀌어도 계속된다.",
  "다 읽으면 감상 보내도 될까요? 다음 책 이야기도 듣고 싶어요.",
  "처음 추천해 주셨던 책도, 돌아가는 길에 바로 펼쳤어요.",
  "비가 조금 잦아들 때까지 여기 같이 있을게요.",
  "오늘까지 이곳을 지켜줘서 고마워요. 다음 이야기는 천천히 해요.",
];
const REPLIES = [
  "잠깐 있다 가셔도 좋아요. 그 상자는 가벼워요. 무거운 건 제가 안쪽에 숨겨놨거든요. 마지막 손님께 일을 시키는 셈인데, 이상하게 오늘은 혼자 정리하는 것보다 덜 어색하네요.",
  "테이프 끝 접어두셨네요. 저 그거 못 찾으면 한참 씨름하는데. 내일 상자를 열 때도 생각나겠어요. 꼭 큰일을 도와줘야 기억에 남는 건 아닌가 봐요.",
  "네. 계약도 끝났고, 좀 지치기도 했어요. 다른 서점에서 주 삼 일만 일해 보려고요. 당장 새 가게를 여는 건 아니에요. 오늘이 지나면, 쉬는 연습부터 해야겠죠.",
  "네, 마지막으로 추천하고 싶어서 빼뒀어요. 《조금 늦은 안부》라는 단편집이에요. 오늘 안 오시면 추천 실패로 남는 거였는데. 취향을 조금은 알 것 같았거든요.",
  "아직도요? 끝이 좀 해졌을 텐데. 책 얘기를 다시 들으러 와주시는 게 좋았어요. 추천한 뒤의 이야기는 손님이 돌아오지 않으면 알 수 없으니까요.",
  "그럼 선물로 받아주세요. 서두르지 않고 읽어도 좋은 책이에요. 다 읽는 동안은 제 추천이 아직 끝나지 않은 셈이겠네요. 그 정도면 오늘 계산대를 일찍 끈 보람도 있고요.",
  "마지막 날이라고 적으려니 무슨 말이든 너무 거창해져요. 그냥 오늘 비가 왔다고 쓸까도 했어요. 오래 남길 말이라고 생각하니까, 오히려 한 글자도 못 쓰겠더라고요.",
  "이 문장으로 남겨둘게요. 주소가 바뀌어도, 라는 부분이 좋아요. 당장 어디로 갈지 몰라도 괜찮다는 말처럼 들려서요. 빈칸을 다 채우지 않아도 되는 문장이네요.",
  "네, 보내주세요. 연락처를 나눠두면 되겠네요. 다 읽고 나서 어떤 장면이 남았는지 듣고 싶어요. 다음 추천은 책방 주인이 아니라, 먼저 읽은 사람으로 해볼게요.",
  "그랬군요. 추천해 드린 책을 펴는 순간까지는 한 번도 못 봤는데. 이제 그 뒤를 조금 알겠어요. 이곳에서 나눈 이야기가 문 안에만 남는 건 아닌가 봐요.",
  "좋아요. 처마가 좁아서 비가 조금 들이치긴 하지만요. 급하게 인사하지 않아도 되겠네요. 열쇠만 챙기면 정말 끝인데, 오늘은 그 마지막 소리가 조금 낯설 것 같아요.",
  "와주셔서 고마워요. 다음 이야기는 천천히 해요. 책을 다 읽기 전이라도, 안부 정도는 괜찮으니까요. 오늘은 여기까지 잘 마친 것 같아요.",
];
const NARRATIONS = [
  "서윤이 상자를 한쪽으로 옮긴다. 반쯤 비어 있는 책장에 따뜻한 불빛이 남아 있다.",
  "짧게 웃은 서윤이 접힌 테이프 끝을 손끝으로 눌러본다. 빈 상자 하나가 조용히 닫힌다.",
  "서윤이 잠깐 손을 멈췄다가, 카운터 쪽을 바라본다.",
  "서윤이 책 표지를 가볍게 쓸어본다. 스탠드 아래로 책갈피의 작은 그림자가 길어진다.",
  "책갈피 끝의 올이 불빛을 받는다. 서윤은 한동안 책 대신 당신 쪽을 바라본다.",
  "서윤이 책을 조심스럽게 건넨다. 카운터 위에는 빈 카드 한 장이 남는다.",
  "서윤이 펜 뚜껑을 열어 카드 옆에 둔다. 작은 탁자 위의 빈칸은 아직 조용하다.",
  "잉크가 마르는 동안 두 사람은 카드를 움직이지 않는다. 창밖의 빗소리가 그 사이를 채운다.",
  "연락처를 나눈 뒤 서윤이 카드를 챙긴다. 시계 쪽으로 잠깐 시선이 머문다.",
  "젖은 골목에 가로등 불빛이 번진다. 서점 창 안쪽은 이제 어둡다.",
  "서윤이 열쇠를 손에 고쳐 쥔다. 처마 끝에서 떨어지는 빗방울 사이에 짧은 침묵이 놓인다.",
  "열쇠가 돌아가고 문이 잠긴다. 서윤은 바로 돌아서지 않는다. 젖은 골목에 두 사람의 발소리가 잠시 머문다.",
];
export const sceneForTurn = (turn: number) =>
  Math.min(4, Math.floor(turn / 3) + 1);
export const initialTurn: TurnResponse = {
  messages: [
    { id: "m_initial_n", turn: 0, kind: "narration", text: SCENE_ENTRIES[0] },
    {
      id: "m_initial_r",
      turn: 0,
      kind: "reply",
      text: "오늘은 책 사러 오셨다고 해도 못 팔아요. 계산대를 먼저 꺼버렸거든요. 마지막 정리 중인데… 잠깐 있다 가실래요?",
    },
  ],
  completed_turns: 0,
  story_time: TIMES[0],
  scene: {
    id: 1,
    name: SCENE_NAMES[0],
    entered: true,
    image_url: "/images/scene-1.svg",
  },
  card_available: false,
  is_final_turn: false,
};
export const mockTurns: TurnResponse[] = INPUTS.map((text, index) => {
  const turn = index + 1;
  const scene = sceneForTurn(turn);
  const entered = [3, 6, 9].includes(turn);
  const messages: Message[] = [
    { id: `m_${turn}_p`, turn, kind: "player", text },
    { id: `m_${turn}_r`, turn, kind: "reply", text: REPLIES[index] },
    { id: `m_${turn}_n`, turn, kind: "narration", text: NARRATIONS[index] },
  ];
  if (turn === 3)
    messages.push({
      id: "m_3_record",
      turn,
      kind: "record",
      record_type: "fact",
      text: "서윤은 다른 서점에서 주 삼 일 일하며 쉬어볼 생각이다.",
    });
  if (turn === 5)
    messages.push({
      id: "m_5_record",
      turn,
      kind: "record",
      record_type: "memory",
      text: "책갈피를 계속 쓰고 있다는 말이 서윤에게 남았다.",
    });
  if (turn === 9)
    messages.push({
      id: "m_9_record",
      turn,
      kind: "record",
      record_type: "promise",
      text: "책을 다 읽으면 감상을 보내기로 하고 연락처를 나눴다.",
    });
  // 전환 응답의 마지막 narration을 진입 서술로 쓰는 규약. 새 필드는 추가하지 않는다.
  if (entered)
    messages.push({
      id: `m_${turn}_entry`,
      turn,
      kind: "narration",
      text: SCENE_ENTRIES[scene - 1],
    });
  return {
    messages,
    completed_turns: turn,
    story_time: TIMES[turn],
    scene: {
      id: scene,
      name: SCENE_NAMES[scene - 1],
      entered,
      image_url: `/images/scene-${scene}.svg`,
    },
    card_available: scene === 3 && turn < 8,
    is_final_turn: turn === 12,
  };
});
export const mockEnding: Ending = {
  title: "문을 닫은 뒤에도 남는 말",
  body: "열쇠가 돌아가는 소리는 생각보다 작았다. 사이책방의 마지막 불빛이 꺼진 뒤에도, 처마 아래에는 아직 두 사람이 서 있었다. 서윤은 손안의 열쇠를 주머니에 넣고 천천히 숨을 내쉬었다.\n\n책갈피를 계속 쓰고 있다는 말이 서윤에게 남았다. 추천한 책이 어디까지 읽혔는지, 어떤 문장 앞에서 멈췄는지. 문이 닫히면 알 수 없을 줄 알았던 이야기들에 작은 길이 생겼다.\n\n창가에서 적은 카드는 서윤이 챙겼다. 어디로 갈지는 아직 정하지 못했지만, 빈칸을 서둘러 채우지 않아도 될 것 같았다. 당신에게 건넨 책에는 끝이 조금 해진 파란 책갈피가 끼워져 있었다.\n\n다 읽으면 감상을 보내기로 했다. 그것은 거창한 약속도, 새로운 시작을 보장하는 말도 아니었다. 다만 다음에 말을 걸어도 되는 이유 하나가 생겼다. 비는 여전히 내렸고, 두 사람은 인사를 조금 천천히 마쳤다.",
  card: { written: true, text: INPUTS[7], author: "player" },
  evidence: [
    {
      message_id: "m_5_p",
      turn: 5,
      story_time: "20:41",
      scene_name: SCENE_NAMES[1],
      quote: INPUTS[4],
      effect:
        "계속 쓰고 있다는 이 말이, 책방 밖에서도 책 이야기를 이어갈 바탕이 되었다.",
    },
    {
      message_id: "m_8_p",
      turn: 8,
      story_time: "20:50",
      scene_name: SCENE_NAMES[2],
      quote: INPUTS[7],
      effect:
        "이 문장이 카드에 남아, 아직 정해지지 않은 다음을 서두르지 않게 했다.",
    },
    {
      message_id: "m_9_p",
      turn: 9,
      story_time: "20:53",
      scene_name: SCENE_NAMES[2],
      quote: INPUTS[8],
      effect:
        "서윤이 제안을 받아들이면서, 다음 감상을 주고받을 구체적인 약속이 남았다.",
    },
  ],
  unresolved: [
    "새 서점의 장소는 정해지지 않았다. 다음 만남의 날짜도 아직 비어 있다.",
  ],
  image: { status: "done", url: "/images/ending.svg" },
};
export const mockSessions: SessionList = {
  sessions: [
    {
      id: "story-3",
      index: 3,
      status: "in_progress",
      completed_turns: 7,
      ending_title: null,
      portrait_url: "/images/portrait-3.svg",
      created_at: "2026-09-07T20:11:00+09:00",
    },
    {
      id: "story-2",
      index: 2,
      status: "completed",
      completed_turns: 12,
      ending_title: mockEnding.title,
      portrait_url: "/images/portrait-2.svg",
      created_at: "2026-09-06T20:11:00+09:00",
    },
    {
      id: "story-1",
      index: 1,
      status: "completed",
      completed_turns: 12,
      ending_title: mockEnding.title,
      portrait_url: "/images/portrait-1.svg",
      created_at: "2026-09-05T20:11:00+09:00",
    },
  ],
};
