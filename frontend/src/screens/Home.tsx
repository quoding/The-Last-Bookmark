import { useState } from 'react';
import type { Session } from '../types/api';
import { Icon } from '../components/Icon';
import { SessionList } from '../components/SessionList';
import s from '../App.module.css';
export function Home({ authenticated, sessions, onVerify, onNew, onOpen, onLogout, listError, onReload }: {
  authenticated: boolean; sessions: Session[]; onVerify: (code: string) => Promise<void>; onNew: () => void; onOpen: (session: Session) => void; onLogout: () => void; listError: string; onReload: () => void;
}) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const continuing = sessions.find(item => item.status !== 'completed');
  async function enter() {
    if (!code.trim() || busy) return;
    setBusy(true); setError('');
    try { await onVerify(code); setCode(''); } catch (error) { setError(error instanceof Error ? error.message : '들어가지 못했어요. 다시 시도해주세요.'); } finally { setBusy(false); }
  }
  return <main className={s.home}>
    <div className={s.homeArt} aria-hidden="true"><div className={s.windowLight}/><div className={s.bookStack}><i/><i/><i/><span/></div><div className={s.homeArtCaption}>한 권의 책이 끝나도<br/>이야기는 남으니까.</div><span className={s.artFoot}>사이책방 · 마지막 영업일</span></div>
    <div className={s.homeContent}><span className={s.eyebrow}>당신과 서윤의 짧은 이야기</span><h1>마지막<br/><span>책갈피</span></h1><div className={s.smallRule}/><p className={s.intro}>오늘 문을 닫는 작은 서점.<br/>마지막 정리를 함께하며,<br/>서로에게 남길 한 문장을 골라보세요.</p><p className={s.duration}><Icon name="book" size={17}/> 약 10~15분 <span>·</span> 20:30 — 21:00</p>
      {!authenticated ? <form className={s.invite} onSubmit={event => { event.preventDefault(); void enter(); }}><label htmlFor="invite">초대 코드</label><div className={s.inlineForm}><input id="invite" value={code} onChange={event => setCode(event.target.value)} placeholder="초대 코드를 입력해주세요" autoComplete="off" disabled={busy} aria-describedby={error ? 'invite-error' : undefined}/><button className={s.primary} disabled={!code.trim() || busy}>{busy ? '확인 중' : '들어가기'}<Icon name="arrow" size={17}/></button></div>{error && <p id="invite-error" className={s.error} role="alert">{error}</p>}<p className={s.fine}>초대받은 분들을 위해 문을 조금 더 열어두었어요.</p></form> : <div className={s.homeActions}>{continuing && <button className={s.primary} onClick={() => onOpen(continuing)}>이어서 하기 <span className={s.buttonMeta}>{continuing.completed_turns}/12</span><Icon name="arrow" size={17}/></button>}<button className={continuing ? s.secondary : s.primary} onClick={onNew}>새 이야기 시작하기 <Icon name="arrow" size={17}/></button><section className={s.previous}><div className={s.sectionLine}><h2>책갈피를 꽂아둔 이야기</h2><span>{sessions.length}</span></div>{listError ? <p className={s.error} role="alert">{listError} <button className={s.textButton} onClick={onReload}>다시 불러오기</button></p> : <SessionList sessions={sessions} onOpen={onOpen}/>}</section><button className={s.textButton} onClick={onLogout}>초대 코드 바꾸기</button></div>}
      <footer className={s.homeFooter}>끝나는 공간에서, 이어지는 마음.</footer>
    </div>
  </main>;
}
