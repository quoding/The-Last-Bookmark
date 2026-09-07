import test from "node:test";
import assert from "node:assert/strict";
import {
  mockTurns,
  initialTurn,
  mockEnding,
  mockSessions,
} from "../src/api/mock.ts";
import { appendTurn, restoreHistory } from "../src/lib/history.ts";
import {
  graphemes,
  limitCard,
  splitTransition,
  timeProgress,
} from "../src/lib/story.ts";
import {
  axes,
  emptyAppearance,
  randomAppearance,
  PRESETS,
} from "../src/lib/presets.ts";

test("12턴, 네 장면 진입, 기록 세 종류와 근거 원문이 연결된다", () => {
  assert.equal(mockTurns.length, 12);
  assert.deepEqual(
    [initialTurn, ...mockTurns]
      .filter((turn) => turn.scene.entered)
      .map((turn) => turn.completed_turns),
    [0, 3, 6, 9],
  );
  assert.deepEqual(
    mockTurns
      .flatMap((turn) => turn.messages)
      .filter((message) => message.kind === "record")
      .map((message) => message.record_type)
      .sort(),
    ["fact", "memory", "promise"],
  );
  assert.equal(
    mockSessions.sessions.filter((session) => session.status === "completed")
      .length,
    2,
  );
  for (const item of mockEnding.evidence)
    assert.equal(
      mockTurns
        .flatMap((turn) => turn.messages)
        .find((message) => message.id === item.message_id)?.text,
      item.quote,
    );
  assert.equal(mockEnding.card.text, mockTurns[7].messages[0].text);
});
test("전환 턴에서 현재 반응은 구분선 앞이고 진입 서술은 마지막 하나다", () => {
  for (const index of [2, 5, 8]) {
    const split = splitTransition(mockTurns[index]);
    assert.ok(split.entry);
    assert.equal(split.reaction[0].kind, "player");
    assert.equal(split.entry, mockTurns[index].messages.at(-1));
    assert.equal(split.reaction.length + 1, mockTurns[index].messages.length);
  }
});
test("멱등 응답을 다시 합쳐도 턴과 구분선이 증가하지 않는다", () => {
  const history = [initialTurn, ...mockTurns.slice(0, 3)];
  const next = appendTurn(history, mockTurns[2]);
  assert.equal(next.length, 4);
  assert.equal(next.filter((turn) => turn.scene.entered).length, 2);
});
test("원문 줄바꿈과 가족 이모지를 보존하면서 보이는 문자 80개를 센다", () => {
  const emoji = "👨‍👩‍👧‍👦";
  assert.equal(graphemes(emoji).length, 1);
  const card = "  안녕,\n다음에도. " + emoji;
  assert.equal(limitCard(card), card);
  assert.equal(graphemes(limitCard(emoji.repeat(81))).length, 80);
  assert.equal(limitCard(emoji.repeat(81)), emoji.repeat(80));
});
test("외형 기본값은 없고 주사위가 일곱 축을 유효한 값으로 채운다", () => {
  assert.ok(Object.values(emptyAppearance()).every((value) => value === ""));
  for (let i = 0; i < 30; i++) {
    const value = randomAppearance();
    assert.equal(Object.keys(value).length, 7);
    assert.ok(
      axes.every((key) =>
        PRESETS[key].options.some(([id]) => id === value[key]),
      ),
    );
  }
});
test("조기 종료 시각은 진행 막대를 끝까지 채우지 않는다", () => {
  assert.equal(timeProgress("20:30"), 0);
  assert.equal(timeProgress("20:45"), 50);
  assert.equal(timeProgress("21:00"), 100);
});
test("복원은 서버의 현재 시각과 원문을 사용하고 과거 이미지 URL을 지어내지 않는다", () => {
  const last = mockTurns[8];
  const state = {
    id: "story",
    status: "in_progress",
    portrait_confirmed: true,
    presets: randomAppearance(),
    scenes: [1, 2, 3, 4].map((id) => ({
      id,
      name: `장면 ${id}`,
      image_url: id === 4 ? last.scene.image_url : null,
    })),
    ...last,
    messages: [initialTurn, ...mockTurns.slice(0, 9)].flatMap(
      (turn) => turn.messages,
    ),
    portrait: {
      status: "done" as const,
      url: null,
      retry_count: 0,
      retry_limit: 2,
    },
  };
  const history = restoreHistory(state, []);
  assert.equal(history.at(-1)?.story_time, "20:53");
  assert.equal(history[0].scene.image_url, null);
  assert.equal(history.at(-1)?.scene.image_url, last.scene.image_url);
  assert.deepEqual(
    history.flatMap((turn) => turn.messages),
    state.messages,
  );
});

test("로컬 캐시가 없어도 서버 scenes의 네 장면 이미지를 복원한다", () => {
  const last = mockTurns[11];
  const scenes = [1, 2, 3, 4].map((id) => ({
    id,
    name: `서버 장면 ${id}`,
    image_url: `/api/images/remote-${id}`,
  }));
  const state = {
    ...last,
    id: "remote",
    status: "completed",
    portrait_confirmed: true,
    presets: randomAppearance(),
    portrait: {
      status: "done" as const,
      url: "/api/images/portrait",
      retry_count: 1,
      retry_limit: 2,
    },
    scenes,
    scene: { ...last.scene, ...scenes[3] },
    messages: [initialTurn, ...mockTurns].flatMap((turn) => turn.messages),
  };
  const history = restoreHistory(state, []);
  assert.deepEqual(
    history
      .filter((turn) => turn.scene.entered)
      .map((turn) => turn.scene.image_url),
    scenes.map((scene) => scene.image_url),
  );
  assert.equal(history[3].scene.name, "서버 장면 2");
  const pending = restoreHistory(
    {
      ...state,
      scenes: scenes.map((scene) => ({ ...scene, image_url: null })),
    },
    history,
  );
  assert.equal(
    pending[0].scene.image_url,
    null,
    "서버가 준비 중으로 돌린 이미지를 오래된 캐시로 덮지 않는다",
  );
});
