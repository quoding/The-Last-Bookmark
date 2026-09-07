"""관리자 전용 API 비용 모니터링. CLAUDE.md 6장 API 계약(프론트 접점)에는
포함되지 않는 별도 도구다. 초대 코드 인증과 무관하게 ADMIN_PASSWORD로만 보호한다.

비용(USD/KRW)은 여기서 계산하지 않는다. 원시 토큰 사용량만 집계해 돌려주고,
단가는 /admin 페이지에서 조회 시점에 입력·수정한다 (LLM_MODEL 실제 단가가
아직 확정되지 않았고, 단가 변경 때마다 서버를 고칠 필요가 없게 하기 위함).
"""

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_503_SERVICE_UNAVAILABLE

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import ApiUsageLog

router = APIRouter()


def _require_admin(x_admin_password: str = Header(default="")) -> None:
    configured = get_settings().admin_password
    if not configured:
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="관리자 페이지가 설정되지 않았습니다.")
    if x_admin_password != configured:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="관리자 비밀번호가 올바르지 않습니다.")


@router.get("/api/admin/usage")
def get_usage(x_admin_password: str = Header(default="")):
    _require_admin(x_admin_password)

    db: DbSession = get_sessionmaker()()
    try:
        rows = db.execute(
            select(
                ApiUsageLog.code_id,
                ApiUsageLog.kind,
                ApiUsageLog.model,
                func.count().label("call_count"),
                func.sum(ApiUsageLog.text_tokens).label("text_tokens"),
                func.sum(ApiUsageLog.image_tokens).label("image_tokens"),
                func.sum(ApiUsageLog.cached_text_tokens).label("cached_text_tokens"),
                func.sum(ApiUsageLog.cached_image_tokens).label("cached_image_tokens"),
                func.sum(ApiUsageLog.output_tokens).label("output_tokens"),
            )
            .group_by(ApiUsageLog.code_id, ApiUsageLog.kind, ApiUsageLog.model)
            .order_by(ApiUsageLog.code_id, ApiUsageLog.kind)
        ).all()
    finally:
        db.close()

    return {
        "usage": [
            {
                "code_id": r.code_id,
                "kind": r.kind,
                "model": r.model,
                "call_count": r.call_count,
                "text_tokens": r.text_tokens or 0,
                "image_tokens": r.image_tokens or 0,
                "cached_text_tokens": r.cached_text_tokens or 0,
                "cached_image_tokens": r.cached_image_tokens or 0,
                "output_tokens": r.output_tokens or 0,
            }
            for r in rows
        ]
    }


_ADMIN_PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>API 비용 모니터링</title>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --border: #2a2f3a;
    --text: #e8eaf0; --muted: #9aa2b1; --accent: #6ea8fe; --accent2: #7ee7c7;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
    background: var(--bg); color: var(--text); padding: 24px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: 13px; margin-bottom: 20px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; margin-bottom: 16px; }
  .panel h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--muted); margin: 0 0 12px; }
  label { display: block; font-size: 12px; color: var(--muted); margin: 10px 0 4px; }
  input[type="password"], input[type="number"] { width: 100%; background: #0d0f14;
    border: 1px solid var(--border); color: var(--text); border-radius: 8px;
    padding: 8px 10px; font-size: 13px; font-family: inherit; }
  .row { display: flex; gap: 10px; }
  .row > div { flex: 1; }
  button { cursor: pointer; border: none; border-radius: 8px; padding: 10px 14px;
    font-size: 13px; font-weight: 600; background: var(--accent); color: #08101f; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; }
  tfoot td { font-weight: 700; color: var(--accent2); border-top: 2px solid var(--border); }
  .status { font-size: 12px; padding: 8px 10px; border-radius: 8px; margin-top: 10px; display: none; }
  .status.show { display: block; }
  .status.error { background: rgba(255,107,107,0.12); color: #ff6b6b; }
  .status.info { background: rgba(110,168,254,0.12); color: var(--accent); }
  .code-group { margin-bottom: 18px; }
  .code-group h3 { font-size: 14px; margin: 0 0 8px; color: var(--accent2); }
</style>
</head>
<body>

<h1>API 비용 모니터링</h1>
<div class="sub">코드별 실제 토큰 사용량 · 단가는 아래에서 직접 입력해 계산합니다. 비용은 서버에 저장되지 않습니다.</div>

<div class="panel">
  <h2>관리자 비밀번호</h2>
  <input type="password" id="adminPassword" placeholder="ADMIN_PASSWORD" />
  <button id="loadBtn" style="margin-top:10px;width:100%;">불러오기</button>
  <div class="status" id="status"></div>
</div>

<div class="panel">
  <h2>단가 설정 ($ / 1M tokens)</h2>
  <div class="row">
    <div><label>LLM 입력</label><input type="number" id="llmIn" value="0" step="0.01" /></div>
    <div><label>LLM 출력</label><input type="number" id="llmOut" value="0" step="0.01" /></div>
  </div>
  <div class="row">
    <div><label>이미지 텍스트 입력</label><input type="number" id="imgTextIn" value="5" step="0.01" /></div>
    <div><label>이미지(참조) 입력</label><input type="number" id="imgImgIn" value="8" step="0.01" /></div>
  </div>
  <div class="row">
    <div><label>이미지 출력</label><input type="number" id="imgOut" value="30" step="0.01" /></div>
    <div><label>환율 (1 USD = ? KRW)</label><input type="number" id="fxRate" value="1400" step="1" /></div>
  </div>
  <div class="sub" style="margin-top:8px;">LLM_MODEL(gpt-5.6-luna)의 실제 단가가 아직 확정되지 않아 기본값은 0입니다. 확정되면 위 값을 채우세요. 이미지 기본값은 gpt-image-2 공식 단가입니다.</div>
</div>

<div id="results"></div>

<script>
const $ = (id) => document.getElementById(id);

function setStatus(msg, type) {
  const el = $("status");
  el.textContent = msg;
  el.className = "status show " + (type || "info");
}

function fmtUsd(n) { return "$" + n.toFixed(4); }
function fmtKrw(n, fx) { return "₩" + Math.round(n * fx).toLocaleString(); }

function computeRowCost(row, pricing) {
  if (row.kind === "llm") {
    const inCost = (row.text_tokens / 1e6) * pricing.llmIn;
    const outCost = (row.output_tokens / 1e6) * pricing.llmOut;
    return inCost + outCost;
  }
  const textCost = (row.text_tokens / 1e6) * pricing.imgTextIn;
  const imgCost = (row.image_tokens / 1e6) * pricing.imgImgIn;
  const outCost = (row.output_tokens / 1e6) * pricing.imgOut;
  return textCost + imgCost + outCost;
}

async function loadUsage() {
  const password = $("adminPassword").value;
  if (!password) { setStatus("비밀번호를 입력하세요.", "error"); return; }

  setStatus("불러오는 중...", "info");
  try {
    const res = await fetch("/api/admin/usage", {
      headers: { "X-Admin-Password": password }
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setStatus("오류: " + (body.detail || res.statusText), "error");
      return;
    }
    const data = await res.json();
    renderResults(data.usage || []);
    setStatus("완료", "info");
  } catch (err) {
    setStatus("요청 실패: " + err.message, "error");
  }
}

function renderResults(rows) {
  const pricing = {
    llmIn: parseFloat($("llmIn").value) || 0,
    llmOut: parseFloat($("llmOut").value) || 0,
    imgTextIn: parseFloat($("imgTextIn").value) || 0,
    imgImgIn: parseFloat($("imgImgIn").value) || 0,
    imgOut: parseFloat($("imgOut").value) || 0,
  };
  const fx = parseFloat($("fxRate").value) || 0;

  const byCode = {};
  for (const row of rows) {
    if (!byCode[row.code_id]) byCode[row.code_id] = [];
    byCode[row.code_id].push(row);
  }

  const container = $("results");
  container.innerHTML = "";
  let grandTotal = 0;

  for (const codeId of Object.keys(byCode).sort()) {
    const codeRows = byCode[codeId];
    let codeTotal = 0;

    const group = document.createElement("div");
    group.className = "panel code-group";
    let html = `<h3>${codeId}</h3><table><thead><tr>
      <th>종류</th><th>모델</th><th>호출 수</th><th>텍스트 토큰</th><th>이미지 토큰</th><th>출력 토큰</th><th>비용</th>
    </tr></thead><tbody>`;

    for (const row of codeRows) {
      const cost = computeRowCost(row, pricing);
      codeTotal += cost;
      html += `<tr>
        <td>${row.kind}</td><td>${row.model}</td><td>${row.call_count}</td>
        <td>${row.text_tokens.toLocaleString()}</td><td>${row.image_tokens.toLocaleString()}</td>
        <td>${row.output_tokens.toLocaleString()}</td><td>${fmtUsd(cost)} · ${fmtKrw(cost, fx)}</td>
      </tr>`;
    }
    html += `</tbody><tfoot><tr><td colspan="6">코드 합계</td><td>${fmtUsd(codeTotal)} · ${fmtKrw(codeTotal, fx)}</td></tr></tfoot></table>`;
    group.innerHTML = html;
    container.appendChild(group);
    grandTotal += codeTotal;
  }

  const totalPanel = document.createElement("div");
  totalPanel.className = "panel";
  totalPanel.innerHTML = `<h2>전체 합계</h2><div style="font-size:20px;font-weight:700;color:var(--accent2);">${fmtUsd(grandTotal)} · ${fmtKrw(grandTotal, fx)}</div>`;
  container.prepend(totalPanel);

  if (rows.length === 0) {
    container.innerHTML = '<div class="panel sub">기록된 사용량이 없습니다.</div>';
  }
}

$("loadBtn").addEventListener("click", loadUsage);
[$("llmIn"), $("llmOut"), $("imgTextIn"), $("imgImgIn"), $("imgOut"), $("fxRate")].forEach((el) => {
  el.addEventListener("input", () => { if ($("adminPassword").value) loadUsage(); });
});
</script>

</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    if not get_settings().admin_password:
        raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="관리자 페이지가 설정되지 않았습니다.")
    return HTMLResponse(_ADMIN_PAGE)
