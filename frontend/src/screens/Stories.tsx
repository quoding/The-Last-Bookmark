import type { Session } from '../types/api';
import { SessionList } from '../components/SessionList';
import { Icon } from '../components/Icon';
import s from '../App.module.css';
export function Stories({ sessions, onOpen, onNew, onHome }: { sessions: Session[]; onOpen: (session: Session) => void; onNew: () => void; onHome: () => void }) {
  return <main className={s.storiesPage}><button className={s.back} onClick={onHome}><Icon name="back" size={16}/> 처음으로</button><span className={s.eyebrow}>서로에게 남긴 문장들</span><h1 className={s.pageTitle}>책갈피를 꽂아둔 이야기</h1><p className={s.pageLead}>같은 책방, 조금씩 다른 마지막.<br/>마무리된 이야기는 그날의 모습 그대로 다시 읽을 수 있어요.</p><SessionList sessions={sessions} onOpen={onOpen}/><div className={s.storiesFoot}><button className={s.primary} onClick={onNew}>새 이야기 시작하기<Icon name="arrow" size={17}/></button><p className={s.fine}>같은 시작에서도 다른 결말이 나옵니다.</p></div></main>;
}
