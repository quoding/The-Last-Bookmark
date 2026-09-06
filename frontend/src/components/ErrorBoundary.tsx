import { Component, type ReactNode } from "react";
import s from "../App.module.css";
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className={s.loadingPage}>
        <h1 className={s.pageTitle}>잠깐, 페이지가 접혔어요.</h1>
        <p className={s.pageLead}>
          저장된 이야기는 그대로 있어요.
          <br />
          화면을 다시 열어 이어서 읽어주세요.
        </p>
        <button className={s.primary} onClick={() => location.reload()}>
          이야기 다시 열기
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
