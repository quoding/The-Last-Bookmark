import type { Ending, Message, Session, TurnResponse } from "../types/api";
import type { Appearance } from "../lib/presets";
import type {
  PortraitStatus,
  SessionStateResponse,
  CardSubmitRequest,
  TurnSubmitRequest,
} from "../types/server";
import {
  initialTurn,
  mockEnding,
  mockSessions,
  mockTurns,
  SCENE_NAMES,
} from "./mock.ts";
import { axes, PRESETS } from "../lib/presets.ts";
import { graphemes } from "../lib/story.ts";

/** 목 서버의 내부 저장소다. 이 객체는 API 응답으로 보내지 않는다. */
interface StoredStory {
  session: Session;
  presets: Appearance;
  portrait: PortraitStatus;
  history: TurnResponse[];
  ending: Ending | null;
  started: boolean;
  cardDecided: boolean;
  card: Ending["card"];
  receipts: Record<string, TurnResponse>;
  sceneReadyAt: number;
  endingReadyAt: number;
}
const prefix = "last-bookmark:mock:v1:";
// Vite의 HMR 쿼리가 달라도 같은 탭의 실패 주입을 공유한다. 새로고침하면 초기화된다.
const faultScope = globalThis as typeof globalThis & {
  [key: symbol]: Record<string, number>;
};
const faults = (faultScope[Symbol.for("last-bookmark.mock.faults")] ??= {});
export function setMockFault(name: string, times = 1) {
  faults[name] = times;
}
function takeFault(name: string) {
  if ((faults[name] ?? 0) > 0) {
    faults[name]--;
    return true;
  }
  return false;
}
const read = <T>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(prefix + key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
};
const write = (key: string, value: unknown) =>
  localStorage.setItem(prefix + key, JSON.stringify(value));
const reply = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const donePortrait = (url: string | null): PortraitStatus => ({
  status: "done",
  url,
  retry_count: 0,
  retry_limit: 2,
});
const seedPresets: Appearance = {
  hair_length: "bob",
  hair_color: "dark_brown",
  bangs: "swept",
  eyes: "soft",
  glasses: "none",
  impression: "calm",
  build: "average",
};
function seed(): Record<string, StoredStory> {
  return Object.fromEntries(
    mockSessions.sessions.map((session) => [
      session.id,
      {
        session: structuredClone(session),
        presets: { ...seedPresets },
        portrait: donePortrait(session.portrait_url),
        history: structuredClone([
          initialTurn,
          ...mockTurns.slice(0, session.completed_turns),
        ]),
        ending:
          session.status === "completed" ? structuredClone(mockEnding) : null,
        started: true,
        cardDecided: session.status === "completed",
        card:
          session.status === "completed"
            ? structuredClone(mockEnding.card)
            : { written: false, text: null, author: null },
        receipts: {},
        sceneReadyAt: 0,
        endingReadyAt: 0,
      },
    ]),
  );
}
function restore(story: StoredStory): SessionStateResponse {
  const turn = story.history.at(-1)!;
  return {
    id: story.session.id,
    status: story.session.status,
    completed_turns: turn.completed_turns,
    story_time: turn.story_time,
    scene: {
      ...turn.scene,
      image_url: story.sceneReadyAt > Date.now() ? null : turn.scene.image_url,
    },
    messages: story.history.flatMap((turn) => turn.messages),
    card_available: turn.scene.id === 3 && !story.cardDecided,
    is_final_turn: story.session.completed_turns === 12,
    portrait: story.portrait,
    portrait_confirmed: story.started,
    presets: story.presets ?? { ...seedPresets },
    scenes: SCENE_NAMES.map((name, index) => ({
      id: index + 1,
      name,
      image_url:
        story.started && story.sceneReadyAt <= Date.now()
          ? `/images/scene-${index + 1}.svg`
          : null,
    })),
  };
}
function endingFor(story: StoredStory): Ending {
  const history = story.history;
  const messages = history.flatMap((turn) => turn.messages);
  const early = story.session.completed_turns < 12;
  const candidates = messages.filter((message) => message.kind === "player");
  const selected =
    candidates.length > 3
      ? [
          candidates[Math.floor(candidates.length / 3)],
          candidates[Math.floor((candidates.length * 2) / 3)],
          candidates.at(-1)!,
        ]
      : candidates;
  const card = story.card;
  const promise = messages.some(
    (message) => message.kind === "record" && message.record_type === "promise",
  );
  const giftRecords = messages.filter(
    (message) =>
      message.kind === "record" &&
      [
        "《조금 늦은 안부》를 선물로 받았다.",
        "책과 책갈피는 서윤이 보관하기로 했다.",
      ].includes(message.text),
  );
  // 고정 7턴 회차의 6턴에는 기록 카드 대신 선물 수락과 전달이 대화로 확정되어 있다.
  const seededGift = history.some(
    (turn) =>
      turn.completed_turns === 6 &&
      turn.messages.some(
        (message) =>
          message.kind === "player" &&
          message.text === "이 책은 고맙게 받을게요. 천천히 읽고 싶어요.",
      ) &&
      turn.messages.some(
        (message) =>
          message.kind === "reply" &&
          message.text.startsWith("그럼 선물로 받아주세요."),
      ),
  );
  const bookAccepted = giftRecords.length
    ? giftRecords.at(-1)!.text === "《조금 늦은 안부》를 선물로 받았다."
    : seededGift;
  const body = early
    ? "사이책방의 시계는 마지막으로 나눈 말의 시각에 머물렀다. 정리가 끝나기 전에, 지금까지의 이야기를 이곳에 모아두었다.\n\n서윤이 잠깐 손을 멈추었던 순간과, 당신이 건넨 말들이 남았다. 더 나누지 않은 대화를 작별 인사로 대신하지는 않았다.\n\n아직 문을 잠그는 소리는 들리지 않았다. 오늘의 끝을 어디까지 함께할지는 빈칸으로 남겨둔다."
    : "열쇠가 돌아가는 소리는 생각보다 작았다. 마지막 조명이 꺼지고 사이책방의 문이 잠겼다. 오늘의 영업은 여기에서 끝났다.\n\n당신이 건넨 말들은 지워지지 않았다. 서윤이 답을 고르던 짧은 침묵과, 문장 사이로 들리던 빗소리가 마지막 시간에 함께 남았다.\n\n" +
      (card.written
        ? "카드에 남긴 문장은 고쳐 쓰지 않은 그대로였다. 서윤은 잉크가 마른 카드를 챙겼다."
        : "카드는 빈 채로 남았다. 마지막 날이라고 해서 모든 칸을 채울 필요는 없었다.") +
      "\n\n" +
      (promise
        ? "책을 다 읽으면 감상을 보내기로 했다. 다음 만남의 날짜까지 정해진 것은 아니지만, 다시 말을 건넬 작은 이유가 남았다."
        : "다음 만남은 정하지 않았다. 아직 하지 않은 약속을 결말에 보태지 않고, 오늘 나눈 이야기만 남겨둔다.") +
      (bookAccepted
        ? " 당신이 받은 책에는 파란 천 책갈피가 끼워져 있었다."
        : " 책과 책갈피는 서윤에게 남아 있다.");
  return {
    title: early
      ? "아직 덮지 않은 페이지"
      : promise
        ? "문을 닫은 뒤에도 남는 말"
        : "오늘의 말이 머문 자리",
    body,
    card: structuredClone(card),
    evidence: selected.map((message) => ({
      message_id: message.id,
      turn: message.turn,
      story_time: history.find((turn) => turn.completed_turns === message.turn)!
        .story_time,
      scene_name: SCENE_NAMES[Math.min(3, Math.floor((message.turn - 1) / 3))],
      quote: message.text,
      effect:
        card.written && message.text === card.text
          ? "직접 남긴 이 문장이 카드에 보존되어, 오늘의 구체적인 기억이 되었다."
          : "이 말이 실제 대화에 남아, 마지막 시간을 되짚는 근거가 되었다.",
    })),
    unresolved: [
      early
        ? "아직 문은 잠기지 않았다. 나누지 않은 대화는 빈칸으로 남아 있다."
        : "새 서점의 장소와 다음 만남의 날짜는 아직 정해지지 않았다.",
    ],
    image: { status: "generating", url: null },
  };
}
function makeTurn(
  story: StoredStory,
  text: string,
  cardRequest?: CardSubmitRequest,
): TurnResponse {
  const turn = story.session.completed_turns + 1;
  const response = structuredClone(mockTurns[turn - 1]);
  const player: Message = { id: `m_${turn}_p`, turn, kind: "player", text };
  const records: Message[] = [];
  let answer =
    "그렇게 말씀하시는군요. 잠깐 생각해 볼게요. 오늘은 정리하느라 말도 서둘러 하고 있었는데, 조금 천천히 들어도 괜찮겠어요.";
  if (turn === 3) {
    answer =
      "이곳은 오늘까지지만, 당장 새 서점을 열 생각은 없어요. 다른 서점에서 주 삼 일 일하면서 조금 쉬어보려고요.";
    records.push({
      id: `m_${turn}_record`,
      turn,
      kind: "record",
      record_type: "fact",
      text: "서윤은 다른 서점에서 주 삼 일 일하며 쉬어볼 생각이다.",
    });
  }
  if (/책갈피/.test(text) && /계속|쓰고/.test(text)) {
    answer =
      "아직도 쓰고 계셨군요. 추천한 책의 그다음 이야기는 돌아와 주셔야 알 수 있거든요. 그렇게 남아 있다니, 조금 안심이 돼요.";
    records.push({
      id: `m_${turn}_record_memory`,
      turn,
      kind: "record",
      record_type: "memory",
      text: "책갈피를 계속 쓰고 있다는 말을 나누었다.",
    });
  }
  if (turn >= 4 && /책/.test(text) && /받을게|받겠|받고 싶/.test(text)) {
    answer =
      "그럼 선물로 받아주세요. 《조금 늦은 안부》예요. 책갈피도 같이 두었어요. 서두르지 않고 읽어도 좋은 책이에요.";
    records.push({
      id: `m_${turn}_record_book`,
      turn,
      kind: "record",
      record_type: "fact",
      text: "《조금 늦은 안부》를 선물로 받았다.",
    });
  } else if (/책/.test(text) && /안 받을|받지 않|거절|가지고 계/.test(text)) {
    answer =
      "괜찮아요. 책은 제가 보관할게요. 꼭 뭔가를 가져가야 기억에 남는 건 아니니까요.";
    records.push({
      id: `m_${turn}_record_book`,
      turn,
      kind: "record",
      record_type: "fact",
      text: "책과 책갈피는 서윤이 보관하기로 했다.",
    });
  }
  if (
    turn >= 7 &&
    /감상 보내도|다 읽으면 감상|연락처를 나/.test(text) &&
    !/않|싫|안 보/.test(text)
  ) {
    answer =
      "네, 다 읽으면 감상을 보내주세요. 연락처를 나눠두면 되겠네요. 어떤 장면이 남았는지 듣고 싶어요.";
    records.push({
      id: `m_${turn}_record_promise`,
      turn,
      kind: "record",
      record_type: "promise",
      text: "책을 다 읽으면 감상을 보내기로 하고 연락처를 나눴다.",
    });
  }
  if (cardRequest)
    answer =
      cardRequest.action === "write"
        ? "이 문장 그대로 남겨둘게요. 잉크가 마를 때까지 잠깐 여기 놓아둘까요. 오래 남길 말이라고 해서 꼭 거창할 필요는 없겠네요."
        : "빈 채로 둘게요. 오늘 다 쓰지 않아도 괜찮겠어요. 펜은 제가 챙겨둘게요.";
  if (turn === 12)
    answer =
      "오늘 와주셔서 고마워요. 건네주신 말들은 잘 기억할게요. 이제 문을 닫을 시간이네요. 오늘은 여기까지 잘 마쳤어요.";
  const entry = response.scene.entered ? response.messages.at(-1)! : undefined;
  response.messages = [
    player,
    { id: `m_${turn}_r`, turn, kind: "reply", text: answer },
    {
      id: `m_${turn}_n`,
      turn,
      kind: "narration",
      text:
        turn === 12
          ? "서윤이 열쇠를 돌려 문을 잠근다. 가로등 불빛이 젖은 바닥 위로 길게 놓인다."
          : "서윤이 잠깐 손을 멈춘다. 문장 사이로 작은 책방의 빗소리가 들린다.",
    },
    ...records,
    ...(entry ? [entry] : []),
  ];
  response.card_available = response.scene.id === 3 && !story.cardDecided;
  if (story.sceneReadyAt > Date.now()) response.scene.image_url = null;
  return response;
}
export async function mockFetch(
  path: string,
  init: RequestInit,
): Promise<Response> {
  const method = init.method ?? "GET";
  const body = typeof init.body === "string" ? JSON.parse(init.body) : {};
  await pause(method === "GET" ? 130 : 550);
  if (!navigator.onLine) throw new TypeError("offline");
  if (path === "/api/auth/verify") {
    const attempts = read<number[]>("attempts", []).filter(
      (time) => Date.now() - time < 60000,
    );
    if (attempts.length >= 5) return reply(null, 429);
    attempts.push(Date.now());
    write("attempts", attempts);
    // 진짜 초대 코드 정답은 없다. 목 모드에서만 임의의 4자 이상 코드로 체험한다.
    if (
      typeof body.code !== "string" ||
      body.code.trim().length < 4 ||
      takeFault("auth")
    )
      return reply(null, 401);
    const bytes = new TextEncoder().encode(body.code);
    const hash = Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      (x) => x.toString(16).padStart(2, "0"),
    ).join("");
    return reply({ token: `mock-${hash}` });
  }
  const token = new Headers(init.headers)
    .get("Authorization")
    ?.replace("Bearer ", "");
  if (!token?.startsWith("mock-")) return reply(null, 401);
  const stories = read<Record<string, StoredStory>>(token, seed());
  const save = () => write(token, stories);
  if (path === "/api/sessions" && method === "GET") {
    if (takeFault("list")) return reply(null, 503);
    save();
    return reply({
      sessions: Object.values(stories)
        .map((story) => story.session)
        .sort((a, b) => b.index - a.index),
    });
  }
  const receiptKey = `${token}:portrait-receipts`;
  const receipts = read<Record<string, { path: string; response: unknown }>>(
    receiptKey,
    {},
  );
  const portraitMutation =
    method === "POST" &&
    (path === "/api/sessions" || path.endsWith("/portrait/retry"));
  if (portraitMutation) {
    if (typeof body.request_id !== "string" || !body.request_id.trim())
      return reply(null, 422);
    const receipt = receipts[body.request_id];
    if (receipt)
      return receipt.path === path ? reply(receipt.response) : reply(null, 409);
  }
  const saveReceipt = (response: unknown) => {
    receipts[body.request_id] = { path, response: structuredClone(response) };
    write(receiptKey, receipts);
  };
  if (path === "/api/sessions" && method === "POST") {
    if (
      !body.presets ||
      !axes.every((key) =>
        PRESETS[key].options.some(([id]) => id === body.presets[key]),
      )
    )
      return reply(null, 422);
    await pause(1000);
    const id = crypto.randomUUID();
    const index =
      Math.max(
        0,
        ...Object.values(stories).map((story) => story.session.index),
      ) + 1;
    const fail = takeFault("portrait");
    const portrait: PortraitStatus = {
      status: fail ? "failed" : "done",
      url: fail ? null : `/images/portrait-${(index % 3) + 1}.svg`,
      retry_count: 0,
      retry_limit: 2,
    };
    stories[id] = {
      session: {
        id,
        index,
        status: "in_progress",
        completed_turns: 0,
        ending_title: null,
        portrait_url: portrait.url,
        created_at: new Date().toISOString(),
      },
      presets: body.presets,
      portrait,
      history: [structuredClone(initialTurn)],
      ending: null,
      started: false,
      cardDecided: false,
      card: { written: false, text: null, author: null },
      receipts: {},
      sceneReadyAt: 0,
      endingReadyAt: 0,
    };
    save();
    const result = { id, index, portrait };
    saveReceipt(result);
    if (takeFault("portrait-after-save")) return reply(null, 503);
    return reply(result);
  }
  const match = path.match(/^\/api\/sessions\/([^/]+)(.*)$/);
  const story = match ? stories[decodeURIComponent(match[1])] : undefined;
  if (!story || !match) return reply(null, 404);
  const action = match[2];
  if (action === "" && method === "DELETE") {
    if (takeFault("delete-not-found")) return reply(null, 404);
    if (takeFault("delete")) return reply(null, 503);
    delete stories[story.session.id];
    save();
    return reply({ status: "deleted", id: story.session.id });
  }
  if (action === "" && method === "GET") {
    if (story.sceneReadyAt <= Date.now())
      story.history.forEach((turn) => {
        turn.scene.image_url = `/images/scene-${turn.scene.id}.svg`;
      });
    save();
    return reply(restore(story));
  }
  if (action === "/portrait/retry") {
    if (
      story.started ||
      (story.portrait.retry_count >= 2 && story.portrait.status === "done")
    )
      return reply(null, 409);
    await pause(1000);
    const fail = takeFault("portrait-retry");
    if (!fail && story.portrait.status === "done") story.portrait.retry_count++;
    story.portrait.status = fail ? "failed" : "done";
    story.portrait.url = fail
      ? null
      : `/images/portrait-${((story.session.index + story.portrait.retry_count) % 3) + 1}.svg`;
    story.session.portrait_url = story.portrait.url;
    save();
    const result = { portrait: story.portrait };
    saveReceipt(result);
    if (takeFault("portrait-retry-after-save")) return reply(null, 503);
    return reply(result);
  }
  if (action === "/start") {
    if (story.portrait.status !== "done") return reply(null, 409);
    if (!story.started) {
      story.started = true;
      story.sceneReadyAt =
        Date.now() + (takeFault("scene-slow") ? 36000 : 1200);
    }
    save();
    const state = restore(story);
    return reply({
      id: state.id,
      completed_turns: state.completed_turns,
      story_time: state.story_time,
      scene: state.scene,
    });
  }
  if (action === "/turns" || action === "/card") {
    const request = body as TurnSubmitRequest | CardSubmitRequest;
    if (!request.request_id) return reply(null, 422);
    if (story.receipts[request.request_id])
      return reply(story.receipts[request.request_id]);
    if (
      !story.started ||
      story.session.status !== "in_progress" ||
      story.session.completed_turns >= 12
    )
      return reply(null, 409);
    if (takeFault("turn")) return reply(null, 503);
    let text = body.text;
    if (action === "/card") {
      if (story.cardDecided || story.history.at(-1)!.scene.id !== 3)
        return reply(null, 409);
      if (
        body.action === "write" &&
        (typeof text !== "string" ||
          !text.trim() ||
          graphemes(text).length > 80)
      )
        return reply(null, 422);
      if (!["write", "leave_blank"].includes(body.action))
        return reply(null, 422);
      story.cardDecided = true;
      story.card =
        body.action === "write"
          ? { written: true, text, author: "player" }
          : { written: false, text: null, author: null };
      if (body.action === "leave_blank") text = "카드를 빈 채로 두기로 했다.";
    }
    if (typeof text !== "string" || !text.trim()) return reply(null, 422);
    const response = makeTurn(
      story,
      text,
      action === "/card" ? body : undefined,
    );
    story.history.push(response);
    story.session.completed_turns = response.completed_turns;
    if (response.is_final_turn) {
      story.session.status = "completed";
      story.ending = endingFor(story);
      story.session.ending_title = story.ending.title;
      story.endingReadyAt =
        Date.now() + (takeFault("image-slow") ? 36000 : 2200);
    }
    story.receipts[request.request_id] = response;
    save();
    if (takeFault("turn-after-save")) return reply(null, 503);
    return reply(response);
  }
  if (action === "/end") {
    if (takeFault("end")) return reply(null, 503);
    if (story.session.status === "in_progress") {
      story.session.status = "ended_early";
      story.ending = endingFor(story);
      story.session.ending_title = story.ending.title;
      story.endingReadyAt = Date.now() + 2200;
      save();
    }
    return reply({ status: story.session.status });
  }
  if (action === "/ending" || action === "/ending/image/retry") {
    if (!story.ending || takeFault("ending-body")) return reply(null, 202);
    if (action.endsWith("/retry")) {
      if (story.ending.image.status === "generating")
        return reply(story.ending);
      story.ending.image = { status: "generating", url: null };
      story.endingReadyAt = Date.now() + 1600;
    }
    if (
      story.ending.image.status === "generating" &&
      Date.now() >= story.endingReadyAt
    )
      story.ending.image = takeFault("ending-image")
        ? { status: "failed", url: null }
        : takeFault("image-refused")
          ? { status: "refused", url: null }
          : {
              status: "done",
              url:
                story.session.completed_turns < 12
                  ? `/images/scene-${story.history.at(-1)!.scene.id}.svg`
                  : "/images/ending.svg",
            };
    save();
    return reply(
      action.endsWith("/retry") ? { image: story.ending.image } : story.ending,
    );
  }
  return reply(null, 404);
}
