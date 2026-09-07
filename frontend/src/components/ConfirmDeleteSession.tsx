import { useEffect, useRef } from "react";
import { Icon } from "./Icon";
import s from "../App.module.css";
export function ConfirmDeleteSession({
  index,
  onClose,
  onConfirm,
  busy,
  error,
}: {
  index: number;
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
      aria-labelledby="delete-title"
      aria-describedby="delete-description"
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
        <h2 id="delete-title">{index}번째 이야기를 삭제할까요?</h2>
        <p id="delete-description">
          이 이야기가 회차 목록에서 사라집니다.
          <br />
          삭제한 이야기는 되돌릴 수 없어요.
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
            취소
          </button>
          <button
            className={`${s.primary} ${s.deleteConfirm}`}
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "삭제하는 중" : "이야기 삭제"}
          </button>
        </div>
      </div>
    </dialog>
  );
}
