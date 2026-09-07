import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import type { Ending, Message, Session, TurnResponse } from "./types/api";
import type {
  CardSubmitRequest,
  SessionCreateResponse,
  SessionCreateRequest,
  PortraitRetryRequest,
  TurnSubmitRequest,
} from "./types/server";
import type { Appearance as AppearanceValue } from "./lib/presets";
import { readLocal, removeLocal, saveLocal, scopedKey } from "./lib/storage";
import { appendTurn, restoreHistory } from "./lib/history";
import { Home } from "./screens/Home";
import { Appearance } from "./screens/Appearance";
import { Conversation } from "./screens/Conversation";
import { EndingScreen } from "./screens/EndingScreen";
import { Stories } from "./screens/Stories";
import { ConfirmDeleteSession } from "./components/ConfirmDeleteSession";
import { Icon } from "./components/Icon";
import s from "./App.module.css";

type Pending =
  | { kind: "turn"; body: TurnSubmitRequest; turn: number }
  | { kind: "card"; body: CardSubmitRequest; turn: number };
type PortraitDraft = {
  value: AppearanceValue;
  result: SessionCreateResponse;
  retryRequest?: PortraitRetryRequest;
};
type OptimisticMessage = { sessionId: string; message: Message };
const routeNow = () => location.hash.slice(1) || "/";
const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "잠시 연결이 끊겼어요. 다시 시도해주세요.";
export default function App() {
  const [route, setRoute] = useState(routeNow);
  const [token, setToken] = useState(
    () => localStorage.getItem("last-bookmark:token") ?? "",
  );
  const [sessions, setSessions] = useState<Session[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteNotice, setDeleteNotice] = useState("");
  const deleteGate = useRef(false);
  const deletedIds = useRef(new Set<string>());
  const [listError, setListError] = useState("");
  const [loading, setLoading] = useState(false);
  const [globalError, setGlobalError] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [turns, setTurns] = useState<TurnResponse[]>([]);
  const [optimistic, setOptimistic] = useState<OptimisticMessage | null>(null);
  const [ending, setEnding] = useState<Ending | null>(null);
  const [portraitDraft, setPortraitDraft] = useState<PortraitDraft | null>(
    () =>
      token
        ? readLocal<PortraitDraft | null>(
            scopedKey(token, "portrait-draft"),
            null,
          )
        : null,
  );
  const [createPending, setCreatePending] =
    useState<SessionCreateRequest | null>(() =>
      token
        ? readLocal<SessionCreateRequest | null>(
            scopedKey(token, "portrait-create-request"),
            null,
          )
        : null,
    );
  const [text, setText] = useState("");
  const [cardText, setCardText] = useState("");
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState("");
  const [endBusy, setEndBusy] = useState(false);
  const [endError, setEndError] = useState("");
  const [endingPending, setEndingPending] = useState(false);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState("");
  const [focusMessage, setFocusMessage] = useState<string | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [reload, setReload] = useState(0);
  const [endingReload, setEndingReload] = useState(0);
  const gate = useRef(false);
  const pending = useRef<Pending | null>(null);
  const endingScroll = useRef<Record<string, number>>({});
  const isAppearanceRoute =
    route === "/appearance" || route.startsWith("/appearance/");
  const routeRef = useRef(route);
  routeRef.current = route;
  const routeMatch = route.match(/^\/(story|ending|appearance)\/([^/]+)$/);
  const sessionId = routeMatch ? decodeURIComponent(routeMatch[2]) : null;
  const activeId = useRef(sessionId);
  activeId.current = sessionId;
  const key = useCallback(
    (suffix: string) => scopedKey(token, suffix),
    [token],
  );
  const navigate = (path: string) => {
    if (location.hash === `#${path}`) setRoute(path);
    else location.hash = path;
  };
  useEffect(() => {
    const handle = () => setRoute(routeNow());
    window.addEventListener("hashchange", handle);
    return () => window.removeEventListener("hashchange", handle);
  }, []);
  useEffect(() => {
    const handle = () => setOnline(navigator.onLine);
    const expired = () => {
      localStorage.removeItem("last-bookmark:token");
      setToken("");
      setGlobalError(
        "초대 코드를 다시 입력해주세요. 이야기는 저장되어 있어요.",
      );
    };
    window.addEventListener("online", handle);
    window.addEventListener("offline", handle);
    window.addEventListener("bookmark-auth-expired", expired);
    return () => {
      window.removeEventListener("online", handle);
      window.removeEventListener("offline", handle);
      window.removeEventListener("bookmark-auth-expired", expired);
    };
  }, []);
  const loadSessions = useCallback(async () => {
    if (!token) return;
    try {
      const list = await api.sessions();
      if (localStorage.getItem("last-bookmark:token") !== token) return;
      setSessions(
        list.sessions
          .filter((item) => !deletedIds.current.has(`${token}:${item.id}`))
          .sort((a, b) => b.index - a.index),
      );
      setListError("");
    } catch (error) {
      setListError(errorText(error));
    }
  }, [token]);
  useEffect(() => {
    void loadSessions();
    setDeleteTarget(null);
    setDeleteNotice("");
    setCreatePending(
      token
        ? readLocal<SessionCreateRequest | null>(
            key("portrait-create-request"),
            null,
          )
        : null,
    );
    setPortraitDraft(
      token
        ? readLocal<PortraitDraft | null>(key("portrait-draft"), null)
        : null,
    );
  }, [token, loadSessions, key]);
  useEffect(() => {
    if (token && route === "/appearance" && portraitDraft && !createPending)
      navigate(`/appearance/${portraitDraft.result.id}`);
  }, [token, route, portraitDraft?.result.id, !!createPending]);
  useEffect(() => {
    if (!token || !sessionId) return;
    let cancelled = false;
    setLoading(true);
    setGlobalError("");
    setEnding(null);
    setSendError("");
    setOptimistic(null);
    setEndError("");
    setImageError("");
    setEndingPending(false);
    async function load() {
      try {
        const [state, list] = await Promise.all([
          api.restore(sessionId!),
          api.sessions(),
        ]);
        if (cancelled) return;
        const item = list.sessions.find((item) => item.id === sessionId);
        if (!item)
          throw new Error(
            "이 이야기를 찾을 수 없어요. 회차 목록에서 다시 골라주세요.",
          );
        if (!state.portrait_confirmed) {
          const previous = readLocal<PortraitDraft | null>(
            key("portrait-draft"),
            null,
          );
          const draft: PortraitDraft = {
            value: state.presets,
            result: {
              id: state.id,
              index: item.index,
              portrait: state.portrait,
            },
            ...(previous?.result.id === state.id && previous.retryRequest
              ? { retryRequest: previous.retryRequest }
              : {}),
          };
          saveLocal(key("portrait-draft"), draft);
          setPortraitDraft(draft);
          removeLocal(key("portrait-create-request"));
          setCreatePending(null);
          setSession(null);
          setTurns([]);
          setSessions(
            list.sessions
              .filter((item) => !deletedIds.current.has(`${token}:${item.id}`))
              .sort((a, b) => b.index - a.index),
          );
          if (!isAppearanceRoute) navigate(`/appearance/${state.id}`);
          return;
        }
        if (isAppearanceRoute) {
          removeLocal(key("portrait-draft"));
          setPortraitDraft(null);
          navigate(`/story/${state.id}`);
        }
        const cached = readLocal<TurnResponse[]>(
          key(`history:${sessionId}`),
          [],
        );
        if (cancelled) return;
        const history = restoreHistory(state, cached);
        saveLocal(key(`history:${sessionId}`), history);
        const previousRequest = readLocal<Pending | null>(
          key(`pending:${sessionId}`),
          null,
        );
        if (previousRequest && previousRequest.turn <= state.completed_turns) {
          removeLocal(key(`pending:${sessionId}`));
          pending.current = null;
        } else {
          pending.current = previousRequest;
          if (previousRequest) {
            setSendError(
              "완료를 확인하지 못한 대화가 있어요. 같은 요청으로 다시 시도해주세요.",
            );
            if (previousRequest.kind === "turn")
              setOptimistic({
                sessionId: state.id,
                message: {
                  id: `optimistic-${previousRequest.body.request_id}`,
                  turn: previousRequest.turn,
                  kind: "player",
                  text: previousRequest.body.text,
                },
              });
          }
        }
        setSession({
          ...item,
          completed_turns: state.completed_turns,
          status: state.status as Session["status"],
        });
        setSessions(
          list.sessions
            .filter((item) => !deletedIds.current.has(`${token}:${item.id}`))
            .sort((a, b) => b.index - a.index),
        );
        setTurns(history);
        setText(
          previousRequest &&
            previousRequest.turn > state.completed_turns &&
            previousRequest.kind === "turn"
            ? previousRequest.body.text
            : readLocal<string>(key(`text:${sessionId}`), ""),
        );
        setCardText(readLocal<string>(key(`card:${sessionId}`), ""));
        setEndingPending(state.status !== "in_progress");
      } catch (error) {
        if (!cancelled) setGlobalError(errorText(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [sessionId, token, reload, key, isAppearanceRoute]);
  useEffect(() => {
    if (
      !session ||
      session.id !== sessionId ||
      session.status === "in_progress"
    )
      return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function poll() {
      try {
        const result = await api.ending(session!.id);
        if (cancelled) return;
        setEnding(result);
        setEndingPending(false);
        setImageBusy(false);
        setGlobalError("");
        failures = 0;
        if (result.image.status === "generating")
          timer = setTimeout(poll, 1800);
      } catch (error) {
        if (cancelled) return;
        failures++;
        if (
          failures < 4 &&
          !(error instanceof ApiError && error.status === 401)
        )
          timer = setTimeout(poll, failures * 1200);
        else {
          setEndingPending(false);
          setGlobalError(
            "마지막 장면을 아직 불러오지 못했어요. 대화는 저장되어 있어요.",
          );
        }
      }
    }
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [session?.id, session?.status, sessionId, endingReload]);
  const refreshImages = useCallback(async () => {
    if (!sessionId || !token) return;
    try {
      const state = await api.restore(sessionId);
      if (activeId.current !== sessionId) return;
      setTurns((old) => {
        const history = restoreHistory(state, old);
        saveLocal(key(`history:${sessionId}`), history);
        return history;
      });
    } catch {
      /* 텍스트와 이전 이미지를 유지하며 다음 폴링에서 다시 확인한다. */
    }
  }, [sessionId, token, key]);
  const storyNeedsImages =
    routeMatch?.[1] === "story" &&
    (turns.length === 0 || turns.some((turn) => !turn.scene.image_url));
  useEffect(() => {
    if (!sessionId || !storyNeedsImages || !online) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      await refreshImages();
      if (!stopped) timer = setTimeout(poll, 2500);
    };
    timer = setTimeout(poll, 1500);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [sessionId, storyNeedsImages, online, refreshImages]);
  function changeText(value: string) {
    setText(value);
    if (session) saveLocal(key(`text:${session.id}`), value);
  }
  function changeCard(value: string) {
    setCardText(value);
    if (session) saveLocal(key(`card:${session.id}`), value);
  }
  function newStory() {
    setPortraitDraft(null);
    setCreatePending(null);
    removeLocal(key("portrait-draft"));
    removeLocal(key("portrait-create-request"));
    setGlobalError("");
    navigate("/appearance");
  }
  function openSession(item: Session) {
    setGlobalError("");
    setFocusMessage(null);
    navigate(
      `/${item.status === "in_progress" ? "story" : "ending"}/${item.id}`,
    );
  }
  async function generate(value: AppearanceValue) {
    if (
      (portraitDraft?.result.portrait.status === "failed" ||
        portraitDraft?.result.portrait.status === "refused") &&
      JSON.stringify(portraitDraft.value) === JSON.stringify(value)
    ) {
      await retryPortrait();
      return;
    }
    if (gate.current) return;
    gate.current = true;
    try {
      const saved = readLocal<SessionCreateRequest | null>(
        key("portrait-create-request"),
        null,
      );
      const request =
        saved && JSON.stringify(saved.presets) === JSON.stringify(value)
          ? saved
          : { request_id: crypto.randomUUID(), presets: value };
      saveLocal(key("portrait-create-request"), request);
      setCreatePending(request);
      const result = await api.create(request);
      const draft = { value, result };
      saveLocal(key("portrait-draft"), draft);
      setPortraitDraft(draft);
      removeLocal(key("portrait-create-request"));
      setCreatePending(null);
      if (routeRef.current.startsWith("/appearance"))
        navigate(`/appearance/${result.id}`);
      void loadSessions();
      if (result.portrait.status !== "done")
        throw new Error(
          "서윤을 그리지 못했어요. 같은 모습으로 다시 시도해주세요. 횟수는 줄어들지 않아요.",
        );
    } finally {
      gate.current = false;
    }
  }
  async function retryPortrait() {
    if (!portraitDraft || gate.current) return;
    gate.current = true;
    try {
      const request = portraitDraft.retryRequest ?? {
        request_id: crypto.randomUUID(),
      };
      const pendingDraft = { ...portraitDraft, retryRequest: request };
      saveLocal(key("portrait-draft"), pendingDraft);
      setPortraitDraft(pendingDraft);
      const result = await api.portraitRetry(portraitDraft.result.id, request);
      const draft: PortraitDraft = {
        value: portraitDraft.value,
        result: { ...portraitDraft.result, portrait: result.portrait },
      };
      saveLocal(key("portrait-draft"), draft);
      setPortraitDraft(draft);
      if (result.portrait.status !== "done")
        throw new Error(
          "그림을 완성하지 못했어요. 같은 모습으로 다시 시도해주세요.",
        );
    } finally {
      gate.current = false;
    }
  }
  async function startStory() {
    if (!portraitDraft) return;
    await api.start(portraitDraft.result.id);
    const id = portraitDraft.result.id;
    removeLocal(key("portrait-draft"));
    setPortraitDraft(null);
    navigate(`/story/${id}`);
    void loadSessions();
  }
  async function submit(request: Pending) {
    if (!session || gate.current || session.status !== "in_progress") return;
    gate.current = true;
    setBusy(true);
    setSendError("");
    const id = session.id;
    pending.current = request;
    if (request.kind === "turn") {
      setOptimistic({
        sessionId: id,
        message: {
          id: `optimistic-${request.body.request_id}`,
          turn: request.turn,
          kind: "player",
          text: request.body.text,
        },
      });
    }
    try {
      saveLocal(key(`pending:${id}`), request);
      const response =
        request.kind === "turn"
          ? await api.turn(id, request.body)
          : await api.card(id, request.body);
      const history = appendTurn(turns, response);
      saveLocal(key(`history:${id}`), history);
      removeLocal(key(`pending:${id}`));
      if (request.kind === "turn") removeLocal(key(`text:${id}`));
      else removeLocal(key(`card:${id}`));
      if (activeId.current !== id) {
        setOptimistic((current) =>
          current?.sessionId === id ? null : current,
        );
        void loadSessions();
        return;
      }
      setTurns(history);
      setOptimistic(null);
      pending.current = null;
      if (request.kind === "turn") {
        setText("");
        removeLocal(key(`text:${id}`));
      } else {
        setCardText("");
        removeLocal(key(`card:${id}`));
      }
      setSession((current) =>
        current
          ? {
              ...current,
              completed_turns: response.completed_turns,
              status: response.is_final_turn ? "completed" : current.status,
            }
          : null,
      );
      if (response.is_final_turn) setEndingPending(true);
      void loadSessions();
    } catch (error) {
      if (activeId.current === id) setSendError(errorText(error));
    } finally {
      gate.current = false;
      setBusy(false);
    }
  }
  function send() {
    if (!session || !text.trim() || pending.current) return;
    void submit({
      kind: "turn",
      body: { request_id: crypto.randomUUID(), text },
      turn: session.completed_turns + 1,
    });
  }
  function sendCard(written: boolean) {
    if (!session || pending.current) return;
    void submit({
      kind: "card",
      body: {
        request_id: crypto.randomUUID(),
        action: written ? "write" : "leave_blank",
        text: written ? cardText : null,
      },
      turn: session.completed_turns + 1,
    });
  }
  async function endStory() {
    if (!session || gate.current) return;
    gate.current = true;
    setEndBusy(true);
    setEndError("");
    const requestKey = key(`end-request:${session.id}`);
    const requestId = readLocal<string>(requestKey, "") || crypto.randomUUID();
    try {
      saveLocal(requestKey, requestId);
      await api.end(session.id, requestId);
      setSession({ ...session, status: "ended_early" });
      setEndingPending(true);
      removeLocal(requestKey);
      void loadSessions();
    } catch (error) {
      setEndError(errorText(error));
    } finally {
      gate.current = false;
      setEndBusy(false);
    }
  }
  async function retryEndingImage() {
    if (
      !session ||
      imageBusy ||
      gate.current ||
      ending?.image.status === "generating"
    )
      return;
    gate.current = true;
    setImageBusy(true);
    setImageError("");
    try {
      const result = await api.retryEndingImage(session.id);
      setEnding((value) => (value ? { ...value, image: result.image } : value));
      setEndingReload((value) => value + 1);
    } catch (error) {
      setImageError(errorText(error));
      setImageBusy(false);
    } finally {
      gate.current = false;
    }
  }
  const viewEnding = () => {
    if (session) navigate(`/ending/${session.id}`);
  };
  const viewConversation = (messageId: string | null = null) => {
    setFocusMessage(messageId);
    if (session) navigate(`/story/${session.id}`);
  };
  const exit = () => {
    navigate("/");
    void loadSessions();
  };
  const askDelete = (item: Session) => {
    setDeleteError("");
    setDeleteNotice("");
    setDeleteTarget(item);
  };
  const deleteSession = async () => {
    if (!deleteTarget || deleteGate.current) return;
    const target = deleteTarget;
    deleteGate.current = true;
    setDeleteBusy(true);
    setDeleteError("");
    try {
      await api.deleteSession(target.id);
      deletedIds.current.add(`${token}:${target.id}`);
      if (localStorage.getItem("last-bookmark:token") !== token) return;
      setSessions((items) => items.filter((item) => item.id !== target.id));
      for (const prefix of [
        "history",
        "pending",
        "text",
        "card",
        "end-request",
      ])
        removeLocal(key(`${prefix}:${target.id}`));
      if (portraitDraft?.result.id === target.id) {
        removeLocal(key("portrait-draft"));
        setPortraitDraft(null);
      }
      if (session?.id === target.id) {
        setSession(null);
        setTurns([]);
        setEnding(null);
        pending.current = null;
      }
      delete endingScroll.current[target.id];
      setDeleteTarget(null);
      setDeleteNotice(`${target.index}번째 이야기를 삭제했어요.`);
    } catch (error) {
      setDeleteError(
        error instanceof ApiError && error.status === 404
          ? "이 이야기를 찾을 수 없거나 삭제할 권한이 없어요. 목록을 새로고침해주세요."
          : "삭제하지 못했어요. 연결을 확인하고 다시 시도해주세요.",
      );
    } finally {
      deleteGate.current = false;
      setDeleteBusy(false);
    }
  };
  const showEnding = route.startsWith("/ending/") && !!token;
  const active = session?.id === sessionId && turns.length > 0;
  return (
    <div className={showEnding ? s.endingBackground : undefined}>
      {!online && (
        <div className={s.offlineBanner} role="status">
          인터넷 연결이 잠시 끊겼어요. 작성하던 말은 그대로 있어요.
        </div>
      )}
      <div className={s.shell}>
        <header className={s.topbar}>
          <button className={s.brand} disabled={busy || endBusy} onClick={exit}>
            <Icon name="bookmark" size={22} /> 마지막 책갈피
          </button>
          <span className={s.topNote}>사이책방의 마지막 저녁</span>
        </header>
        {globalError && (
          <div className={s.globalError} role="alert">
            <span>{globalError}</span>
            {token && (
              <button
                className={s.textButton}
                onClick={() => {
                  setGlobalError("");
                  if (
                    session?.id === sessionId &&
                    session?.status !== "in_progress"
                  )
                    setEndingReload((value) => value + 1);
                  else setReload((value) => value + 1);
                }}
              >
                다시 불러오기
              </button>
            )}
            <button
              className={s.iconButton}
              onClick={() => setGlobalError("")}
              aria-label="안내 닫기"
            >
              <Icon name="close" size={16} />
            </button>
          </div>
        )}
        {!token || route === "/" ? (
          <Home
            authenticated={!!token}
            sessions={sessions}
            onVerify={async (code) => {
              const result = await api.verify(code);
              localStorage.setItem("last-bookmark:token", result.token);
              setToken(result.token);
              setGlobalError("");
            }}
            onNew={newStory}
            onOpen={openSession}
            onDelete={askDelete}
            onLogout={() => {
              localStorage.removeItem("last-bookmark:token");
              setToken("");
              setSessions([]);
              setSession(null);
              navigate("/");
            }}
            listError={listError}
            onReload={() => void loadSessions()}
          />
        ) : isAppearanceRoute &&
          sessionId &&
          (loading || portraitDraft?.result.id !== sessionId) ? (
          <main className={s.loadingPage}>
            <p role="status">서윤의 모습을 다시 불러오고 있어요</p>
            <button className={s.textButton} onClick={exit}>
              처음으로 돌아가기
            </button>
          </main>
        ) : isAppearanceRoute ? (
          <Appearance
            key={sessionId ?? "new"}
            onBack={exit}
            onGenerate={generate}
            onRetry={retryPortrait}
            onStart={startStory}
            portrait={portraitDraft?.result.portrait.url ?? null}
            remaining={
              portraitDraft
                ? Math.max(
                    0,
                    portraitDraft.result.portrait.retry_limit -
                      portraitDraft.result.portrait.retry_count,
                  )
                : 2
            }
            restoredAppearance={portraitDraft?.value ?? createPending?.presets}
            pendingOperation={
              portraitDraft?.retryRequest
                ? "retry"
                : createPending
                  ? "generate"
                  : undefined
            }
            portraitFailed={
              portraitDraft?.result.portrait.status === "failed" ||
              portraitDraft?.result.portrait.status === "refused"
            }
          />
        ) : route === "/stories" ? (
          <Stories
            sessions={sessions}
            onOpen={openSession}
            onDelete={askDelete}
            onNew={newStory}
            onHome={exit}
          />
        ) : loading || !active ? (
          <main className={s.loadingPage}>
            <span className={s.loadingDots} aria-hidden="true">
              ···
            </span>
            <p role="status">
              {globalError
                ? "이야기를 불러오지 못했어요."
                : "꽂아둔 책갈피를 찾고 있어요"}
            </p>
            <button className={s.textButton} onClick={exit}>
              처음으로 돌아가기
            </button>
          </main>
        ) : showEnding ? (
          ending ? (
            <EndingScreen
              ending={ending}
              messages={turns.flatMap((turn) => turn.messages)}
              storyTime={turns.at(-1)!.story_time}
              index={session!.index}
              onConversation={() => viewConversation()}
              onQuote={viewConversation}
              onSessions={() => {
                void loadSessions();
                navigate("/stories");
              }}
              onNew={newStory}
              onRetryImage={() => void retryEndingImage()}
              retryBusy={imageBusy}
              imageError={imageError}
              savedScroll={endingScroll.current[session!.id] ?? 0}
              onScroll={(top) => {
                endingScroll.current[session!.id] = top;
              }}
            />
          ) : (
            <main className={s.loadingPage}>
              <p role="status">마지막 장면을 정리하고 있어요</p>
              <button
                className={s.textButton}
                onClick={() => viewConversation()}
              >
                마지막 대화 다시 읽기
              </button>
            </main>
          )
        ) : (
          <Conversation
            key={session!.id}
            session={session!}
            turns={turns}
            optimisticMessage={
              optimistic?.sessionId === session!.id ? optimistic.message : null
            }
            readOnly={session!.status !== "in_progress"}
            text={text}
            onText={changeText}
            cardText={cardText}
            onCardText={changeCard}
            onSend={send}
            onCard={sendCard}
            busy={busy}
            error={sendError}
            onRetry={() => {
              if (pending.current) void submit(pending.current);
            }}
            onExit={exit}
            onEnd={() => void endStory()}
            endBusy={endBusy}
            endError={endError}
            endingPending={endingPending}
            endingReady={!!ending}
            onEnding={viewEnding}
            focusMessage={focusMessage}
            onFocusHandled={() => setFocusMessage(null)}
            onRefreshImages={() => void refreshImages()}
          />
        )}
        {token && deleteTarget && (
          <ConfirmDeleteSession
            index={deleteTarget.index}
            busy={deleteBusy}
            error={deleteError}
            onClose={() => setDeleteTarget(null)}
            onConfirm={() => void deleteSession()}
          />
        )}
        <span className={s.srOnly} role="status">
          {deleteNotice}
        </span>
        <span className={s.srOnly} role="status">
          {busy ? "응답을 기다리는 중입니다." : ""}
        </span>
      </div>
    </div>
  );
}
