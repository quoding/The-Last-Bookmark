import { useState } from "react";
import { graphemes, limitCard } from "../lib/story";
import { Icon } from "./Icon";
import s from "../App.module.css";
export function CardEditor({
  text,
  onChange,
  onClose,
  onSubmit,
  busy,
}: {
  text: string;
  onChange: (text: string) => void;
  onClose: () => void;
  onSubmit: (written: boolean) => void;
  busy: boolean;
}) {
  const [composing, setComposing] = useState(false);
  const count = graphemes(text).length;
  return (
    <section className={s.cardEditor} aria-label="빈 카드 편집기">
      <div className={s.sectionLine}>
        <h2>당신이 남길 한 문장</h2>
        <button
          className={s.iconButton}
          aria-label="카드 편집기 닫기"
          disabled={busy}
          onClick={onClose}
        >
          <Icon name="close" size={16} />
        </button>
      </div>
      <textarea
        aria-label="카드 문장"
        placeholder="오래 남기고 싶은 말을 적어주세요."
        value={text}
        disabled={busy}
        onCompositionStart={() => setComposing(true)}
        onCompositionEnd={(event) => {
          setComposing(false);
          onChange(limitCard(event.currentTarget.value));
        }}
        onChange={(event) =>
          onChange(
            composing ? event.target.value : limitCard(event.target.value),
          )
        }
      />
      <div className={s.cardEditorFoot}>
        <span>{count}/80자 · 확정하면 대화 1회가 진행돼요</span>
        <button
          className={s.textButton}
          disabled={busy}
          onClick={() => onSubmit(false)}
        >
          빈 채로 두기
        </button>
        <button
          className={s.primary}
          disabled={busy || !text.trim() || count > 80 || composing}
          onClick={() => onSubmit(true)}
        >
          이 문장으로 남기기
        </button>
      </div>
    </section>
  );
}
