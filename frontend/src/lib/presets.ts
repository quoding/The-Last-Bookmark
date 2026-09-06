export const PRESETS = {
  hair_length: {
    label: "머리 길이",
    options: [
      ["bob", "단발"],
      ["shoulder", "어깨 길이"],
      ["long", "등까지 오는 긴 머리"],
      ["short", "짧은 층 있는 머리"],
    ],
  },
  hair_color: {
    label: "머리 색",
    options: [
      ["dark_brown", "짙은 갈색"],
      ["black", "검정"],
      ["ash_brown", "애쉬 브라운"],
      ["auburn", "어두운 적갈색"],
    ],
  },
  bangs: {
    label: "앞머리",
    options: [
      ["full", "있음"],
      ["swept", "없음(옆으로 넘긴)"],
      ["center", "가운데 가르마"],
    ],
  },
  eyes: {
    label: "눈매",
    options: [
      ["sharp", "또렷한"],
      ["droopy", "처진"],
      ["languid", "나른한"],
      ["soft", "부드러운"],
    ],
  },
  glasses: {
    label: "안경",
    options: [
      ["round", "얇은 둥근 테"],
      ["square", "사각 뿔테"],
      ["none", "없음"],
    ],
  },
  impression: {
    label: "인상",
    options: [
      ["calm", "차분한"],
      ["warm", "다정한"],
      ["cool", "서늘한"],
    ],
  },
  build: {
    label: "키·체형",
    options: [
      ["petite", "작고 아담한"],
      ["average", "보통"],
      ["tall", "크고 마른"],
    ],
  },
} as const;
export type Appearance = { [K in keyof typeof PRESETS]: string };
export const axes = Object.keys(PRESETS) as (keyof Appearance)[];
export const emptyAppearance = (): Appearance =>
  Object.fromEntries(axes.map((key) => [key, ""])) as Appearance;
export const randomAppearance = (): Appearance =>
  Object.fromEntries(
    axes.map((key) => {
      const options = PRESETS[key].options;
      return [key, options[Math.floor(Math.random() * options.length)][0]];
    }),
  ) as Appearance;
export const appearanceSummary = (value: Appearance) =>
  axes
    .map(
      (key) =>
        `${PRESETS[key].label} ${PRESETS[key].options.find((option) => option[0] === value[key])?.[1] ?? "미선택"}`,
    )
    .join(" · ");
