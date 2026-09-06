import { useState } from "react";
import {
  axes,
  emptyAppearance,
  PRESETS,
  randomAppearance,
  appearanceSummary,
  type Appearance as AppearanceValue,
} from "../lib/presets";
import { Icon } from "../components/Icon";
import { SceneImage } from "../components/SceneImage";
import s from "../App.module.css";
export function Appearance({
  onBack,
  onGenerate,
  onRetry,
  onStart,
  portrait,
  remaining,
  restoredAppearance,
  portraitFailed = false,
}: {
  onBack: () => void;
  onGenerate: (value: AppearanceValue) => Promise<void>;
  onRetry: () => Promise<void>;
  onStart: () => Promise<void>;
  portrait: string | null;
  remaining: number;
  restoredAppearance?: AppearanceValue;
  portraitFailed?: boolean;
}) {
  const [value, setValue] = useState<AppearanceValue>(
    restoredAppearance ?? emptyAppearance(),
  );
  const [phase, setPhase] = useState<"select" | "portrait">(
    portrait || portraitFailed ? "portrait" : "select",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(
    portraitFailed
      ? "서윤을 그리지 못했어요. 같은 모습으로 다시 시도해주세요."
      : "",
  );
  const [operation, setOperation] = useState<"generate" | "retry" | "start">(
    "generate",
  );
  const complete = axes.every((key) => value[key]);
  async function run(action: "generate" | "retry" | "start") {
    if (busy) return;
    setBusy(true);
    setError("");
    setOperation(action);
    if (action === "generate") setPhase("portrait");
    try {
      await (action === "generate"
        ? onGenerate(value)
        : action === "retry"
          ? onRetry()
          : onStart());
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "잠시 연결이 끊겼어요. 다시 시도해주세요.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className={s.appearancePage}>
      <button className={s.back} onClick={onBack} disabled={busy}>
        <Icon name="back" size={16} /> 책방으로 돌아가기
      </button>
      <div className={s.appearanceHeading}>
        <span className={s.eyebrow}>이야기를 시작하기 전에</span>
        <h1 className={s.pageTitle}>당신이 기억할 서윤</h1>
        <p className={s.pageLead}>
          고른 모습이 그림에 반영됩니다.
          <br />
          성격과 이야기는 정해져 있어요.
        </p>
      </div>
      {phase === "select" ? (
        <div className={s.appearanceLayout}>
          <section className={s.presetPanel}>
            <div className={s.sectionLine}>
              <h2>어떤 모습으로 만날까요?</h2>
              <button
                className={s.dice}
                onClick={() => setValue(randomAppearance())}
              >
                <Icon name="dice" size={18} /> 주사위로 고르기
              </button>
            </div>
            <div className={s.presetGrid}>
              {axes.map((key) => (
                <label key={key} className={s.presetLabel} htmlFor={key}>
                  {PRESETS[key].label}
                  <select
                    id={key}
                    value={value[key]}
                    onChange={(event) =>
                      setValue({ ...value, [key]: event.target.value })
                    }
                  >
                    <option value="" disabled>
                      선택해주세요
                    </option>
                    {PRESETS[key].options.map(([id, label]) => (
                      <option key={id} value={id}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className={s.selectionSummary} aria-live="polite">
              <span className={s.eyebrow}>고른 모습</span>
              <p>
                {complete
                  ? appearanceSummary(value)
                  : "일곱 가지를 고르면, 당신이 고른 서윤의 모습을 이곳에 모아둘게요."}
              </p>
            </div>
            <button
              className={s.primary}
              disabled={!complete || busy}
              onClick={() => void run("generate")}
            >
              이 모습으로 시작 <Icon name="arrow" size={17} />
            </button>
          </section>
          <aside className={s.characterNote}>
            <span className={s.noteTab} />
            <span className={s.eyebrow}>사이책방의 주인</span>
            <h2>한서윤</h2>
            <p>
              책을 권하는 말은 익숙하지만,
              <br />
              자신의 바람은 조금 늦게 꺼내는 사람.
            </p>
            <p>
              오늘은 이 작은 책방의
              <br />
              마지막 영업일입니다.
            </p>
            <div className={s.smallRule} />
            <span className={s.fine}>
              27세 · 크림색 니트와 짙은 초록색 앞치마
            </span>
          </aside>
        </div>
      ) : (
        <div className={s.portraitLayout}>
          <SceneImage
            url={portrait}
            label="서윤의 초상화"
            generating={busy && operation !== "start"}
            failed={!!error && operation !== "start"}
            onRetry={() => void run(operation)}
            busy={busy}
          />
          <div className={s.portraitCopy}>
            <span className={s.eyebrow}>곧 만나게 될 사람</span>
            <h2 className={s.pageTitle}>
              마지막 손님을
              <br />
              기다리고 있어요.
            </h2>
            <p className={s.pageLead}>{appearanceSummary(value)}</p>
            {error && (
              <p className={s.error} role="alert">
                {error}
              </p>
            )}
            <div className={s.verticalActions}>
              <button
                className={s.primary}
                onClick={() => void run("start")}
                disabled={
                  busy || !portrait || (!!error && operation !== "start")
                }
              >
                {busy && operation === "start"
                  ? "책방의 문을 여는 중이에요"
                  : "이 모습으로 시작하기"}
                <Icon name="arrow" size={17} />
              </button>
              {error ? (
                <button
                  className={s.secondary}
                  disabled={busy}
                  onClick={() => void run(operation)}
                >
                  같은 요청 다시 시도하기
                </button>
              ) : (
                <button
                  className={s.secondary}
                  disabled={busy || remaining === 0 || !portrait}
                  onClick={() => void run("retry")}
                >
                  다시 그리기{" "}
                  <span className={s.fine}>남은 횟수 {remaining}/2</span>
                </button>
              )}
              <button
                className={s.textButton}
                disabled={busy}
                onClick={() => {
                  setPhase("select");
                  setError("");
                }}
              >
                외형 다시 고르기
              </button>
            </div>
            <p className={s.fine}>
              선택한 모습으로 장면마다 그림이 이어집니다.
            </p>
          </div>
        </div>
      )}
    </main>
  );
}
