import { useEffect, useRef, useState, type RefObject } from "react";
import type { Ending, Message } from "../types/api";
import { Icon } from "./Icon";
import s from "../App.module.css";
/** 다음 카드 하나만 관찰한다. 여러 카드가 뷰포트 안에 있어도 동시에 공개하지 않는다. */
export function EvidenceTrail({
  evidence,
  messages,
  scrollRoot,
  onQuote,
}: {
  evidence: Ending["evidence"];
  messages: Message[];
  scrollRoot: RefObject<HTMLDivElement>;
  onQuote: (id: string) => void;
}) {
  const [revealed, setRevealed] = useState(0);
  const slots = useRef<(HTMLDivElement | null)[]>([]);
  const nextAllowed = useRef(0);
  useEffect(() => {
    const target = slots.current[revealed];
    if (!target) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const root = scrollRoot.current;
    const inspect = () => {
      if (!root) return;
      const bounds = root.getBoundingClientRect();
      // 재진입으로 이미 지나친 카드도 순서를 따라 공개한다. 긴 인용문에도 교차 비율을 요구하지 않는다.
      const reached =
        target.getBoundingClientRect().top <
        bounds.bottom - bounds.height * 0.18;
      if (!reached && timer) {
        clearTimeout(timer);
        timer = undefined;
      }
      if (reached && !timer)
        timer = setTimeout(
          () => {
            nextAllowed.current = Date.now() + 620;
            setRevealed((count) => count + 1);
          },
          Math.max(80, nextAllowed.current - Date.now()),
        );
    };
    const observer = new IntersectionObserver(inspect, { root, threshold: 0 });
    observer.observe(target);
    root?.addEventListener("scroll", inspect, { passive: true });
    window.addEventListener("resize", inspect);
    inspect();
    return () => {
      observer.disconnect();
      root?.removeEventListener("scroll", inspect);
      window.removeEventListener("resize", inspect);
      if (timer) clearTimeout(timer);
    };
  }, [revealed, scrollRoot, evidence.length]);
  return (
    <section className={s.evidenceSection} aria-labelledby="evidence-title">
      <div className={s.evidenceHeading}>
        <Icon name="bookmark" size={22} />
        <span className={s.eyebrow}>당신의 말이 닿은 곳</span>
        <h2 id="evidence-title">이 결말에 남은 대화</h2>
        <p>
          지나온 말들을 천천히 되짚어보세요.
          <br />
          당신의 문장은, 이 이야기 안에 그대로 남아 있어요.
        </p>
      </div>
      {evidence.length === 0 ? (
        <p className={s.emptyEvidence}>
          아직 결말의 근거로 남길 대화는 없어요.
          <br />
          비어 있는 자리도 그대로 남겨둡니다.
        </p>
      ) : (
        <div className={s.evidenceTrail}>
          {evidence.map((item, index) => {
            const source = messages.find(
              (message) =>
                message.id === item.message_id && message.kind === "player",
            );
            const quote = source?.text ?? item.quote;
            const visible = index < revealed;
            return (
              <div
                className={s.evidenceSlot}
                ref={(element) => {
                  slots.current[index] = element;
                }}
                key={item.message_id}
              >
                <span
                  className={`${s.trailDot} ${visible ? s.trailDotVisible : ""}`}
                  aria-hidden="true"
                />
                <button
                  className={`${s.evidenceCard} ${visible ? s.evidenceVisible : ""}`}
                  tabIndex={visible ? 0 : -1}
                  aria-hidden={!visible}
                  disabled={!source}
                  onClick={() => onQuote(item.message_id)}
                  aria-label={`${item.story_time} ${item.scene_name}. ${quote}. 해당 대화로 이동`}
                >
                  <span className={s.evidenceMeta}>
                    <time>{item.story_time}</time>
                    <span>·</span>
                    <span>{item.scene_name}</span>
                    <span className={s.evidenceNumber}>
                      {String(index + 1).padStart(2, "0")}
                    </span>
                  </span>
                  <blockquote>
                    <span aria-hidden="true" className={s.quoteMark}>
                      “
                    </span>
                    <span className={s.quoteText}>{quote}</span>
                    <span aria-hidden="true" className={s.quoteEnd}>
                      ”
                    </span>
                  </blockquote>
                  <span className={s.evidenceEffect}>{item.effect}</span>
                  <span className={s.quoteLink}>
                    {source
                      ? "이 말이 있던 순간으로"
                      : "원문 기록을 불러오지 못했어요"}
                    <Icon name="arrow" size={16} />
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      )}
      <p className={s.trailEnd}>당신이 건넨 말에서, 이 결말까지.</p>
    </section>
  );
}
