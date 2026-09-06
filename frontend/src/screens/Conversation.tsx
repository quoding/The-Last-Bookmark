import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { Session, TurnResponse } from '../types/api';
import { SceneImage } from '../components/SceneImage';
import { Icon } from '../components/Icon';
import { MessageBubble } from '../components/MessageBubble';
import { CardEditor } from '../components/CardEditor';
import { ConfirmEnd } from '../components/ConfirmEnd';
import { HINTS, splitTransition, timeProgress } from '../lib/story';
import s from '../App.module.css';
export function Conversation({ session, turns, readOnly, text, onText, cardText, onCardText, onSend, onCard, busy, error, onRetry, onExit, onEnd, endBusy, endError, endingPending, endingReady, onEnding, focusMessage, onFocusHandled, onRefreshImages }: {
  session: Session; turns: TurnResponse[]; readOnly: boolean; text: string; onText: (text: string) => void; cardText: string; onCardText: (text: string) => void; onSend: () => void; onCard: (written: boolean) => void; busy: boolean; error: string; onRetry: () => void; onExit: () => void; onEnd: () => void; endBusy: boolean; endError: string; endingPending: boolean; endingReady: boolean; onEnding: () => void; focusMessage: string | null; onFocusHandled: () => void; onRefreshImages: () => void;
}) {
  const current = turns.at(-1)!;
  const root = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const bottom = useRef(true);
  const initial = useRef(true);
  const lastCount = useRef(current.completed_turns);
  const [newMessages, setNewMessages] = useState(false);
  const [viewScene, setViewScene] = useState(turns[0]);
  const [menu, setMenu] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [cardOpen, setCardOpen] = useState(false);
  const [highlighted, setHighlighted] = useState<string | null>(focusMessage);
  const input = useRef<HTMLTextAreaElement>(null);
  const locked = busy || endBusy || endingPending || endingReady || !!error;
  function readScroll() {
    const element = root.current;
    if (!element) return;
    bottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 65;
    if (bottom.current) setNewMessages(false);
    const edge = element.getBoundingClientRect().top + Math.min(140, element.clientHeight * .25);
    let active = turns[0];
    for (const marker of element.querySelectorAll<HTMLElement>('[data-scene-entry]')) {
      if (marker.getBoundingClientRect().top <= edge) active = turns.find(turn => turn.completed_turns === Number(marker.dataset.sceneEntry)) ?? active;
    }
    setViewScene(active);
  }
  function toBottom() { const element = root.current; if (!element) return; element.scrollTop = element.scrollHeight; bottom.current = true; setNewMessages(false); readScroll(); }
  useLayoutEffect(() => {
    if (focusMessage) {
      const target = document.getElementById(`message-${focusMessage}`);
      if (target && root.current) {
        const container = root.current;
        container.scrollTop += target.getBoundingClientRect().top - container.getBoundingClientRect().top - 95;
        target.focus({ preventScroll: true }); setHighlighted(focusMessage); readScroll(); onFocusHandled(); initial.current = false;
      }
      return;
    }
    if (initial.current) { toBottom(); initial.current = false; }
    else if (lastCount.current !== current.completed_turns) { if (bottom.current) toBottom(); else setNewMessages(true); }
    lastCount.current = current.completed_turns;
  }, [current.completed_turns, focusMessage]);
  useEffect(() => { if (!highlighted) return; const timer = setTimeout(() => setHighlighted(null), 4500); return () => clearTimeout(timer); }, [highlighted]);
  useEffect(() => { if (current.scene.id !== 3 || !current.card_available) setCardOpen(false); }, [current.scene.id, current.card_available]);
  useEffect(() => { if (!menu) return; const listener = (event: PointerEvent) => { if (!menuRef.current?.contains(event.target as Node)) setMenu(false); }; const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenu(false); }; document.addEventListener('pointerdown', listener); document.addEventListener('keydown', key); return () => { document.removeEventListener('pointerdown', listener); document.removeEventListener('keydown', key); }; }, [menu]);
  const past = viewScene.scene.id !== current.scene.id;
  const displayScene = turns.find(turn => turn.scene.id === viewScene.scene.id && turn.scene.image_url) ?? viewScene;
  return <main className={s.conversationLayout}><aside className={s.imageColumn}><SceneImage url={displayScene.scene.image_url} label={`${viewScene.scene.name}의 서윤`} onRetry={onRefreshImages}/><div className={s.imageCaption}><span>{past ? '책갈피를 되짚는 중' : '지금, 이 장면'}</span><p>{viewScene.story_time} · {viewScene.scene.name}</p></div>{readOnly && <details className={s.imageAlbum}><summary>이 이야기의 그림 6장</summary><div><button onClick={() => setViewScene({ ...current, scene: { ...current.scene, id: 0, name: '서윤의 초상화', image_url: session.portrait_url } })}>초상화</button>{turns.filter(turn => turn.scene.entered).map(turn => <button key={turn.scene.id} onClick={() => setViewScene(turn)}>{turn.scene.name}</button>)}<button onClick={onEnding}>마지막 그림</button></div></details>}</aside>
    <section className={s.conversationPanel} aria-label="서윤과의 대화"><header className={s.storyHeader}><div><div className={s.clockLine}><time>{current.story_time}</time><span>사이책방</span></div><p>21:00 문 닫는 시간</p></div><div className={s.headerRight}><span>대화 {current.completed_turns}/12 완료</span>{readOnly ? <button className={s.textButton} onClick={onEnding}>결말로 돌아가기</button> : <div className={s.menuWrap} ref={menuRef}><button className={s.iconButton} aria-label="이야기 메뉴" aria-expanded={menu} disabled={busy || endBusy || endingPending} onClick={() => setMenu(!menu)}><Icon name="menu"/></button>{menu && <div className={s.menu}><button onClick={onExit}>저장하고 나가기</button>{!endingReady && <button onClick={() => { setMenu(false); setConfirm(true); }}>여기서 이야기 마무리하기</button>}</div>}</div>}</div><div className={s.timeTrack} role="progressbar" aria-label="이야기 속 시간" aria-valuemin={0} aria-valuemax={30} aria-valuenow={Math.round(timeProgress(current.story_time) * .3)} aria-valuetext={`${current.story_time}, 21:00 문 닫는 시간`}><span style={{ width: `${timeProgress(current.story_time)}%` }}/></div></header>
      {readOnly && <div className={s.readOnlyNote}>마무리된 이야기입니다. 남겨진 대화와 그림을 다시 읽어보세요.</div>}
      <div className={s.logWrap}><div className={s.conversationLog} ref={root} onScroll={readScroll} tabIndex={0} aria-label="대화 기록"><div className={s.logIntro}>오늘 문을 닫는 작은 서점.<br/>마지막 정리를 함께하는 시간입니다.</div>{turns.map((turn, index) => {
        const { reaction, entry } = splitTransition(turn);
        const divider = <div className={s.sceneDivider} data-scene-entry={turn.completed_turns}><span>{turn.story_time} · {turn.scene.name}</span></div>;
        return <div key={turn.completed_turns}>{index === 0 && divider}{reaction.map((message, i) => <MessageBubble key={message.id} message={message} portrait={session.portrait_url} highlighted={message.id === highlighted} consecutive={i > 0 && reaction[i - 1].kind === 'reply'}/>)}{entry && <>{divider}<MessageBubble message={entry} portrait={session.portrait_url} highlighted={entry.id === highlighted} consecutive={false}/></>}</div>;
      })}{busy && <div className={s.typing} role="status"><img className={s.chatAvatar} src={session.portrait_url ?? '/images/portrait-1.svg'} alt=""/><span><i/><i/><i/></span><span className={s.srOnly}>서윤이 답하고 있어요</span></div>}{endingPending && <p className={s.endingPending} role="status">마지막 장면을 정리하고 있어요</p>}{endingReady && <div className={s.openEnding}><Icon name="bookmark" size={22}/><p>당신이 남긴 말들이<br/>하나의 결말이 되었어요.</p><button className={s.primary} onClick={onEnding}>결말 펼쳐보기<Icon name="arrow" size={17}/></button></div>}</div>{newMessages && <button className={s.newMessages} onClick={toBottom}>새 대화 <span>↓</span></button>}</div>
      {!readOnly && !endingReady && !endingPending && <div className={s.composer}>{current.completed_turns === 11 && <p className={s.lastHint}>이제 마지막 대화예요. 남기고 싶은 말이나 행동을 전해주세요.</p>}{error && <p className={s.error} role="alert">{error} <button className={s.textButton} onClick={onRetry} disabled={busy}>같은 요청 다시 시도하기</button></p>}{current.scene.id === 3 && current.card_available && (cardOpen ? <CardEditor text={cardText} onChange={onCardText} onClose={() => setCardOpen(false)} onSubmit={onCard} busy={locked}/> : <button className={s.cardTrigger} disabled={locked} onClick={() => setCardOpen(true)}><Icon name="bookmark" size={16}/> 카드에 한 문장 남기기<span>↗</span></button>)}<div className={s.hints}>{HINTS[current.scene.id]?.map(hint => <button key={hint} disabled={locked} onClick={() => { onText(hint); input.current?.focus(); }}>{hint}</button>)}</div><form className={s.inputBox} onSubmit={event => { event.preventDefault(); if (!locked && text.trim()) onSend(); }}><textarea ref={input} aria-label="서윤에게 전할 말" value={text} disabled={locked} rows={2} placeholder="서윤에게 말을 건네거나, 하고 싶은 행동을 적어보세요." onChange={event => onText(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); if (!locked && text.trim()) onSend(); } }}/><button className={s.sendButton} aria-label="보내기" disabled={locked || !text.trim()}><Icon name="arrow" size={20}/></button></form><div className={s.inputFoot}><span>{busy ? '서윤이 답하고 있어요. 잠시만 기다려주세요.' : '어떤 말이든, 당신의 문장으로.'}</span><span>Enter 보내기 · Shift+Enter 줄바꿈</span></div></div>}
    </section>{confirm && <ConfirmEnd onClose={() => setConfirm(false)} onConfirm={onEnd} busy={endBusy} error={endError}/>}</main>;
}
