import type { Session } from "../types/api";
import { Icon } from "./Icon";
import { imageURL } from "../api/client";
import s from "../App.module.css";
export function SessionList({
  sessions,
  onOpen,
}: {
  sessions: Session[];
  onOpen: (session: Session) => void;
}) {
  return (
    <div className={s.sessionList}>
      {sessions.length === 0 ? (
        <p className={s.muted}>
          아직 남겨진 이야기가 없어요. 첫 페이지를 열어보세요.
        </p>
      ) : (
        sessions.map((session) => (
          <button
            className={s.sessionRow}
            key={session.id}
            onClick={() => onOpen(session)}
          >
            <img
              className={s.avatar}
              src={imageURL(session.portrait_url) ?? "/images/portrait-1.svg"}
              alt={`${session.index}번째 이야기의 서윤`}
            />
            <span className={s.sessionInfo}>
              <span className={s.eyebrow}>
                {session.index}번째 이야기{" "}
                <span className={s.status}>
                  {session.status !== "in_progress" ? "완료" : "진행 중"}
                </span>
              </span>
              <strong>
                {session.status !== "in_progress"
                  ? session.ending_title
                  : `진행 중 (${session.completed_turns}/12)`}
              </strong>
              <span className={s.date}>
                {session.created_at.slice(0, 10).replaceAll("-", ".")}
              </span>
            </span>
            <Icon name="chevron" size={16} />
          </button>
        ))
      )}
    </div>
  );
}
