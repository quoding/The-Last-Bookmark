import { test, expect, type Page } from "@playwright/test";
async function enter(page: Page) {
  await page.goto("/");
  await page.getByLabel("초대 코드", { exact: true }).fill("reading-room");
  await page.getByRole("button", { name: "들어가기", exact: true }).click();
  await expect(page.getByRole("button", { name: /이어서 하기/ })).toBeVisible();
}
async function fault(page: Page, name: string) {
  await page.evaluate(async (faultName) => {
    // @ts-expect-error Vite resolves this development-only module.
    const module = await import("/src/api/mock-server.ts");
    module.setMockFault(faultName);
  }, name);
}
test("초대, 미선택 외형, 주사위, 재생성 두 번, 대화 시작", async ({ page }) => {
  await enter(page);
  await page
    .getByRole("button", { name: "새 이야기 시작하기", exact: true })
    .click();
  await expect(page.getByRole("combobox")).toHaveCount(7);
  for (const select of await page.getByRole("combobox").all())
    await expect(select).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "이 모습으로 시작", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "주사위로 고르기" }).click();
  await expect(
    page.getByRole("button", { name: "이 모습으로 시작", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "이 모습으로 시작", exact: true })
    .click();
  await expect(page.getByText("서윤을 그리는 중이에요")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "이 모습으로 시작하기", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: /다시 그리기.*남은 횟수 2/ }).click();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 1/ }),
  ).toBeEnabled();
  await page.getByRole("button", { name: /다시 그리기.*남은 횟수 1/ }).click();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 0/ }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "이 모습으로 시작하기", exact: true })
    .click();
  await expect(page.getByText("대화 0/12 완료")).toBeVisible();
  await expect(page.getByLabel("서윤에게 전할 말")).toBeVisible();
  await page.screenshot({
    path: "test-results/conversation-desktop.png",
    fullPage: true,
  });
});
test("초상화 실패는 재생성 횟수를 소비하지 않는다", async ({ page }) => {
  await enter(page);
  await page
    .getByRole("button", { name: "새 이야기 시작하기", exact: true })
    .click();
  await page.getByRole("button", { name: "주사위로 고르기" }).click();
  await fault(page, "portrait");
  await page
    .getByRole("button", { name: "이 모습으로 시작", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "같은 요청 다시 시도하기" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "같은 요청 다시 시도하기" }).click();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 2/ }),
  ).toBeEnabled();
});
test("응답 유실 뒤 새로고침해도 턴이 중복되지 않고 카드 원문이 엔딩에 남는다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await page.getByRole("button", { name: "카드에 한 문장 남기기" }).click();
  const sentence = "  다시,\n천천히 만나요. 👨‍👩‍👧‍👦  ";
  await page.getByLabel("카드 문장", { exact: true }).fill(sentence);
  await fault(page, "turn-after-save");
  await page
    .getByRole("button", { name: "이 문장으로 남기기", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "같은 요청 다시 시도하기" }),
  ).toBeVisible();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await page.getByRole("button", { name: "같은 요청 다시 시도하기" }).click();
  await expect(page.getByText("대화 8/12 완료")).toBeVisible();
  await page.reload();
  await expect(page.getByText("대화 8/12 완료")).toBeVisible();
  await page.getByLabel("이야기 메뉴").click();
  await page
    .getByRole("button", { name: "여기서 이야기 마무리하기", exact: true })
    .click();
  await page.getByRole("button", { name: "결말 보기", exact: true }).click();
  await page.getByRole("button", { name: "결말 펼쳐보기" }).click();
  await expect(
    page.getByRole("heading", { name: "아직 덮지 않은 페이지" }),
  ).toBeVisible();
  await expect(page.getByText("20:50, 사이책방에서")).toBeVisible();
  const cardQuote = page.locator("blockquote").first();
  expect(await cardQuote.textContent()).toBe(sentence);
  await page.reload();
  expect(await page.locator("blockquote").first().textContent()).toBe(sentence);
});
test("위쪽 대화를 읽는 동안 전송 응답이 스크롤을 빼앗지 않는다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  const log = page.getByLabel("대화 기록", { exact: true });
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await log.evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  await page.getByLabel("서윤에게 전할 말").fill("오늘 비가 조용하네요.");
  await page.getByRole("button", { name: "보내기", exact: true }).click();
  await expect(page.getByText("대화 8/12 완료")).toBeVisible();
  expect(await log.evaluate((element) => element.scrollTop)).toBe(0);
  await expect(page.getByRole("button", { name: /새 대화/ })).toBeVisible();
  await page.getByRole("button", { name: /새 대화/ }).click();
  expect(await log.evaluate((element) => element.scrollTop)).toBeGreaterThan(
    100,
  );
});
test("엔딩 근거가 순차 공개되고 원문 턴으로 돌아가며 과거 회차는 읽기 전용이다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /2번째 이야기/ }).click();
  await expect(
    page.getByRole("heading", { name: "문을 닫은 뒤에도 남는 말" }),
  ).toBeVisible();
  const cards = page.locator('button[aria-label$="해당 대화로 이동"]');
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).not.toBeVisible();
  const scroller = page.getByLabel("결말과 이 결말에 남은 대화", {
    exact: true,
  });
  await scroller.evaluate((element) => {
    const card = element.querySelector(
      'button[aria-label$="해당 대화로 이동"]',
    )!;
    element.scrollTop +=
      card.getBoundingClientRect().top -
      element.getBoundingClientRect().top -
      100;
  });
  await expect(cards.first()).toBeVisible();
  await expect(cards.nth(2)).not.toBeVisible();
  await page.screenshot({
    path: "test-results/ending-evidence.png",
    fullPage: true,
  });
  await cards.first().click();
  const quote = page.locator('[data-message-id="m_5_p"]');
  await expect(quote).toBeFocused();
  await expect(quote).toContainText("책갈피, 계속 쓰고 있어요.");
  await expect(page.getByLabel("서윤에게 전할 말")).toHaveCount(0);
  await expect(page.getByLabel("이야기 메뉴")).toHaveCount(0);
  await page.getByRole("button", { name: "결말로 돌아가기" }).click();
  await expect(
    page.getByRole("heading", { name: "이 결말에 남은 대화" }),
  ).toBeVisible();
});
test("모바일에서도 화면 폭을 넘지 않는다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await enter(page);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});
test("완료된 모든 턴과 구분선 네 개, 장면 이미지 되짚기를 복원한다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /2번째 이야기/ }).click();
  const scroller = page.getByLabel("결말과 이 결말에 남은 대화", {
    exact: true,
  });
  await expect(scroller).toBeVisible();
  await scroller.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await page
    .getByRole("button", { name: "대화 다시 보기", exact: true })
    .click();
  await expect(page.getByText("대화 12/12 완료")).toBeVisible();
  await expect(page.locator("[data-scene-entry]")).toHaveCount(4);
  const log = page.getByLabel("대화 기록", { exact: true });
  await log.evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(
    page.getByRole("img", { name: "마지막 손님의 서윤", exact: true }),
  ).toBeVisible();
  await log.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(
    page.getByRole("img", { name: "문을 닫기 전에의 서윤", exact: true }),
  ).toBeVisible();
  await page.getByText("이 이야기의 그림 6장", { exact: true }).click();
  await page.getByRole("button", { name: "초상화", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "서윤의 초상화", exact: true }),
  ).toBeVisible();
});
test("엔딩 이미지 실패와 재생성 중에도 본문과 카드가 유지된다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await fault(page, "ending-image");
  await page.getByLabel("이야기 메뉴").click();
  await page
    .getByRole("button", { name: "여기서 이야기 마무리하기", exact: true })
    .click();
  await page.getByRole("button", { name: "결말 보기", exact: true }).click();
  await page.getByRole("button", { name: "결말 펼쳐보기" }).click();
  await expect(
    page.getByRole("heading", { name: "아직 덮지 않은 페이지" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "그림 다시 만들기", exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await page
    .getByRole("button", { name: "그림 다시 만들기", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "아직 덮지 않은 페이지" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "이 이야기의 마지막 그림", exact: true }),
  ).toBeVisible({ timeout: 10000 });
});
test("새로고침한 초상화 화면이 이미지와 남은 횟수를 복원한다", async ({
  page,
}) => {
  await enter(page);
  await page
    .getByRole("button", { name: "새 이야기 시작하기", exact: true })
    .click();
  await page.getByRole("button", { name: "주사위로 고르기" }).click();
  await page
    .getByRole("button", { name: "이 모습으로 시작", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 2/ }),
  ).toBeEnabled();
  await page.getByRole("button", { name: /다시 그리기.*남은 횟수 2/ }).click();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 1/ }),
  ).toBeEnabled();
  await page.reload();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 1/ }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "이 모습으로 시작하기", exact: true }),
  ).toBeEnabled();
});
test("빈 카드 확정만 턴을 소비하며 문장을 지어내지 않는다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  await page.getByRole("button", { name: "카드에 한 문장 남기기" }).click();
  await page.getByLabel("카드 문장", { exact: true }).fill("   ");
  await expect(
    page.getByRole("button", { name: "이 문장으로 남기기" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "카드 편집기 닫기" }).click();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await page.getByRole("button", { name: "카드에 한 문장 남기기" }).click();
  await page.getByRole("button", { name: "빈 채로 두기", exact: true }).click();
  await expect(page.getByText("대화 8/12 완료")).toBeVisible();
  await page.getByLabel("이야기 메뉴").click();
  await page
    .getByRole("button", { name: "여기서 이야기 마무리하기", exact: true })
    .click();
  await page.getByRole("button", { name: "결말 보기", exact: true }).click();
  await page.getByRole("button", { name: "결말 펼쳐보기" }).click();
  await expect(
    page.getByText("카드는 빈 채로 남았다.", { exact: true }),
  ).toBeVisible();
});
test("이미지가 30초 지연되어도 대화는 계속 가능하고 안내만 바뀐다", async ({
  page,
}) => {
  await enter(page);
  await page
    .getByRole("button", { name: "새 이야기 시작하기", exact: true })
    .click();
  await page.getByRole("button", { name: "주사위로 고르기" }).click();
  await page
    .getByRole("button", { name: "이 모습으로 시작", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "이 모습으로 시작하기", exact: true }),
  ).toBeEnabled();
  await page.clock.install();
  await fault(page, "scene-slow");
  await page
    .getByRole("button", { name: "이 모습으로 시작하기", exact: true })
    .click();
  await expect(page.getByText("대화 0/12 완료")).toBeVisible();
  await expect(page.getByLabel("서윤에게 전할 말")).toBeEnabled();
  await page.clock.fastForward(31000);
  await expect(
    page.getByText(
      "그림을 만드는 중이에요. 완성되면 이 회차에서 확인할 수 있어요",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("서윤에게 전할 말")).toBeEnabled();
});
test("실패 직후 새로고침하면 원문과 동일 요청을 복원한다", async ({ page }) => {
  await enter(page);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  const original = "  조금 천천히,\n이야기해요.  ";
  await page.getByLabel("서윤에게 전할 말").fill(original);
  await fault(page, "turn");
  await page.getByRole("button", { name: "보내기", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "같은 요청 다시 시도하기" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await expect(page.getByLabel("서윤에게 전할 말")).toHaveValue(original);
  await page.getByRole("button", { name: "같은 요청 다시 시도하기" }).click();
  await expect(page.getByText("대화 8/12 완료")).toBeVisible();
  expect(await page.locator('[data-message-id="m_8_p"] p').textContent()).toBe(
    original,
  );
});
test("마지막 입력 안내에서 12턴 엔딩까지 진행하며 새 질문을 남기지 않는다", async ({
  page,
}) => {
  await enter(page);
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  for (let turn = 8; turn <= 12; turn++) {
    await expect(page.getByLabel("서윤에게 전할 말")).toBeEnabled();
    if (turn === 12)
      await expect(
        page.getByText(
          "이제 마지막 대화예요. 남기고 싶은 말이나 행동을 전해주세요.",
        ),
      ).toBeVisible();
    await page
      .getByLabel("서윤에게 전할 말")
      .fill("오늘의 이야기를 기억할게요.");
    await page.getByRole("button", { name: "보내기", exact: true }).click();
    await expect(page.getByText(`대화 ${turn}/12 완료`)).toBeVisible();
  }
  await expect(page.locator("[data-scene-entry]")).toHaveCount(4);
  expect(
    await page.locator('[data-message-id="m_12_r"] p').textContent(),
  ).not.toContain("?");
  await page.getByRole("button", { name: "결말 펼쳐보기" }).click();
  await expect(page.getByText("21:00, 사이책방에서")).toBeVisible();
  await expect(
    page.getByText(/당신이 받은 책에는 파란 천 책갈피가 끼워져 있었다/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "오늘의 말이 머문 자리" }),
  ).toBeVisible();
});

test("전환 응답이 기록 카드로 끝나도 장면 구분선과 이미지가 유지된다", async ({
  page,
}) => {
  await enter(page);
  await page.evaluate(() => {
    const token = localStorage.getItem("last-bookmark:token")!;
    const key = `last-bookmark:mock:v1:${token}`;
    const stories = JSON.parse(localStorage.getItem(key)!);
    for (const turn of stories["story-3"].history) {
      if (![3, 6].includes(turn.completed_turns)) continue;
      turn.messages = turn.messages.filter(
        (message: { id: string }) => !message.id.endsWith("_entry"),
      );
      turn.messages.push({
        id: `record-tail-${turn.completed_turns}`,
        turn: turn.completed_turns,
        kind: "record",
        record_type: "memory",
        text: "지금 나눈 말을 기억해두었다.",
      });
    }
    localStorage.setItem(key, JSON.stringify(stories));
  });
  await page.getByRole("button", { name: /이어서 하기/ }).click();
  await expect(page.getByText("대화 7/12 완료")).toBeVisible();
  await expect(page.locator("[data-scene-entry]")).toHaveCount(3);
  await expect(page.locator('[data-scene-entry="3"]')).toContainText(
    "20:37 · 남겨둔 책",
  );
  await expect(page.locator('[data-scene-entry="6"]')).toContainText(
    "20:45 · 쓰지 못한 한 문장",
  );
  await expect(
    page.getByRole("img", { name: "쓰지 못한 한 문장의 서윤", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator("[data-scene-entry]")).toHaveCount(3);
});

test("초상화 생성 거부를 재시도할 때 기존 회차와 잔여 횟수를 유지한다", async ({
  page,
}) => {
  await enter(page);
  await page
    .getByRole("button", { name: "새 이야기 시작하기", exact: true })
    .click();
  await page.getByRole("button", { name: "주사위로 고르기" }).click();
  await page
    .getByRole("button", { name: "이 모습으로 시작", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "이 모습으로 시작하기", exact: true }),
  ).toBeEnabled();
  const before = await page.evaluate(() => {
    const token = localStorage.getItem("last-bookmark:token")!;
    const draftKey = `last-bookmark:${token}:portrait-draft`;
    const storyKey = `last-bookmark:mock:v1:${token}`;
    const draft = JSON.parse(localStorage.getItem(draftKey)!);
    const stories = JSON.parse(localStorage.getItem(storyKey)!);
    draft.result.portrait.status = "refused";
    draft.result.portrait.url = null;
    stories[draft.result.id].portrait = draft.result.portrait;
    localStorage.setItem(draftKey, JSON.stringify(draft));
    localStorage.setItem(storyKey, JSON.stringify(stories));
    return { id: draft.result.id, count: Object.keys(stories).length };
  });
  await page.reload();
  await page
    .getByRole("button", { name: "같은 요청 다시 시도하기", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: /다시 그리기.*남은 횟수 2/ }),
  ).toBeEnabled();
  const after = await page.evaluate(() => {
    const token = localStorage.getItem("last-bookmark:token")!;
    const draft = JSON.parse(
      localStorage.getItem(`last-bookmark:${token}:portrait-draft`)!,
    );
    const stories = JSON.parse(
      localStorage.getItem(`last-bookmark:mock:v1:${token}`)!,
    );
    return { id: draft.result.id, count: Object.keys(stories).length };
  });
  expect(after).toEqual(before);
});
