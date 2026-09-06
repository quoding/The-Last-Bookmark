import type { Message } from "../types/api";
import { Icon } from "./Icon";
import { imageURL } from "../api/client";
import s from "../App.module.css";
const labels = {
  promise: "약속이 기록되었습니다",
  fact: "알게 된 사실",
  memory: "기억에 남을 순간",
};
export function MessageBubble({
  message,
  portrait,
  highlighted,
  consecutive,
}: {
  message: Message;
  portrait: string | null;
  highlighted: boolean;
  consecutive: boolean;
}) {
  return (
    <div
      id={`message-${message.id}`}
      data-message-id={message.id}
      className={`${s.message} ${s[message.kind]} ${highlighted ? s.highlighted : ""}`}
      tabIndex={highlighted ? -1 : undefined}
    >
      {message.kind === "reply" && (
        <>
          <div className={s.profileSlot}>
            {!consecutive && (
              <img
                src={imageURL(portrait) ?? "/images/portrait-1.svg"}
                alt=""
                className={s.chatAvatar}
              />
            )}
          </div>
          <div className={s.replyContent}>
            {!consecutive && <span className={s.speaker}>서윤</span>}
            <p className={s.bubble}>{message.text}</p>
          </div>
        </>
      )}
      {message.kind === "player" && (
        <>
          <span className={s.srOnly}>당신: </span>
          <p className={s.bubble}>{message.text}</p>
        </>
      )}
      {message.kind === "narration" && <p>{message.text}</p>}
      {message.kind === "record" && (
        <div className={s.recordCard}>
          <Icon name="bookmark" size={17} />
          <div>
            <span>{labels[message.record_type]}</span>
            <p>{message.text}</p>
          </div>
        </div>
      )}
    </div>
  );
}
