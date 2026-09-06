import { useEffect, useRef } from "react";
import { Icon } from "./Icon";
import s from "../App.module.css";
export function ConfirmEnd({
  onClose,
  onConfirm,
  busy,
  error,
}: {
  onClose: () => void;
  onConfirm: () => void;
  busy: boolean;
  error: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement as HTMLElement;
    dialog.showModal();
    return () => {
      dialog.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={s.dialog}
      aria-labelledby="end-title"
      aria-describedby="end-description"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !busy) onClose();
      }}
    >
      <div className={s.dialogInside}>
        <Icon name="bookmark" size={26} />
        <h2 id="end-title">여기에 책갈피를 꽂을까요?</h2>
        <p id="end-description">
          지금까지의 이야기로 결말을 만듭니다.
          <br />
          남은 대화는 진행되지 않습니다.
        </p>
        {error && (
          <p className={s.error} role="alert">
            {error}
          </p>
        )}
        <div className={s.dialogActions}>
          <button
            className={s.secondary}
            onClick={onClose}
            disabled={busy}
            autoFocus
          >
            계속 이야기하기
          </button>
          <button className={s.primary} disabled={busy} onClick={onConfirm}>
            {busy ? "이야기를 정리하는 중" : "결말 보기"}
          </button>
        </div>
      </div>
    </dialog>
  );
}
