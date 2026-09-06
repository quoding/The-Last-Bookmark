import { useEffect, useState } from 'react';
import { imageURL } from '../api/client';
import s from '../App.module.css';
export function SceneImage({ url, label, generating = false, failed = false, onRetry, busy = false }: { url: string | null; label: string; generating?: boolean; failed?: boolean; onRetry?: () => void; busy?: boolean }) {
  url = imageURL(url);
  const [visible, setVisible] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [slow, setSlow] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setLoadFailed(false); setSlow(false);
    if (!url || generating || failed) return;
    let cancelled = false;
    const img = new Image();
    img.onload = () => { if (!cancelled) setVisible(current => { if (current !== url) setPrevious(current); return url; }); };
    img.onerror = () => { if (!cancelled) setLoadFailed(true); };
    img.src = url;
    return () => { cancelled = true; };
  }, [url, generating, failed, attempt]);
  const waiting = generating || (!failed && !loadFailed && (!url || visible !== url));
  useEffect(() => { if (!waiting) return; const timer = setTimeout(() => setSlow(true), 30000); return () => clearTimeout(timer); }, [waiting, url]);
  useEffect(() => { if (!previous) return; const timer = setTimeout(() => setPrevious(null), 850); return () => clearTimeout(timer); }, [previous]);
  return <div className={s.imageFrame} aria-busy={waiting}>
    {previous && <img className={s.previousImage} src={previous} alt=""/>}
    {visible && !waiting && !failed && !loadFailed && <img key={visible} className={s.sceneImage} src={visible} alt={label}/>}
    {(waiting || failed || loadFailed) && <div className={`${s.imageState} ${waiting ? s.skeleton : ''}`} role="status"><div className={s.imageOutline}/><p>{failed || loadFailed ? '그림을 불러오지 못했어요.' : slow ? '그림을 만드는 중이에요. 완성되면 이 회차에서 확인할 수 있어요' : label === '서윤의 초상화' ? '서윤을 그리는 중이에요' : '이 장면을 그리는 중이에요'}</p>{(failed || loadFailed) && <button className={s.secondary} disabled={busy} onClick={() => { if (loadFailed) setAttempt(value => value + 1); else onRetry?.(); }}>{busy ? '그리는 중이에요' : loadFailed ? '그림 다시 불러오기' : '그림 다시 만들기'}</button>}</div>}
    <div className={s.imageGradient}/>
  </div>;
}
