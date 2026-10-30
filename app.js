// 小航 front end. Flow modeled on NTU 學習規劃辦公室:
//   首頁 → 會談前（議題、方向清楚度、成績單／興趣測驗）→ 會談 → 整理＋學生自己寫下一步 → 自評表 → 會談紀錄
// All student data stays in this browser (localStorage); the server keeps nothing.
"use strict";

const STORE_KEY = "lp-state-v2";
const DEMO = window.DEMO || null;   // only the static GitHub Pages build sets this (web/demo.js)
const HOLLAND_ORDER = ["R", "I", "A", "S", "E", "C"];   // hexagon order
const THINKING = ["小航正在想…", "正在翻資料…", "正在整理你的側寫…"];
const CLARITY = ["完全沒頭緒", "有點模糊", "有一些想法", "蠻清楚的", "非常清楚"];
// drawn faces for the 1–5 clarity scale (no emoji: they clash with the hand-drawn mascot)
const FACE_FILL = ["#f1ebe4", "#f7e4d2", "#ffe2c8", "#ffcfa6", "#ffb27a"];
const FACE_MOUTH = [
  "M34 67q4-5 8 0t8 0t8 0t8 0",    // 1 wavy: confused
  "M38 69q12-9 24 0",               // 2 small frown
  "M38 66h24",                      // 3 flat
  "M37 62q13 11 26 0",              // 4 smile
  "M34 60q16 16 32 0",              // 5 big smile
];
function faceSVG(level) {
  const i = level - 1;
  const eyes = level === 5
    ? `<path d="M29 46q6.5-8 13 0M58 46q6.5-8 13 0" stroke="#3b2f2a" stroke-width="4.5" fill="none" stroke-linecap="round"/>`
    : `<circle cx="36" cy="45" r="4.5" fill="#3b2f2a"/><circle cx="64" cy="45" r="4.5" fill="#3b2f2a"/>`;
  const cheeks = level >= 4 ? `<ellipse cx="24" cy="58" rx="6" ry="4" fill="#f2897a" opacity=".45"/><ellipse cx="76" cy="58" rx="6" ry="4" fill="#f2897a" opacity=".45"/>` : "";
  return `<svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="44" fill="${FACE_FILL[i]}"/>${eyes}${cheeks}
    <path d="${FACE_MOUTH[i]}" stroke="#3b2f2a" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
const ICONS = {
  grades: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M14 3v4h4M9 12h6M9 16h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  interest: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M15.5 8.5l-2 5-5 2 2-5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>`,
  done: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 12.5l2.8 2.8L16.5 9.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
};
const HELPFUL = ["更了解自己", "知道有哪些選擇", "知道下一步要做什麼", "解決了一個煩惱"];
const PENDING = ["還沒開始", "進行中"];
const LIST_LABELS = [
  ["goals", "目標", "goal"],
  ["strong_subjects", "擅長", "good"],
  ["weak_subjects", "比較吃力", "weak"],
  ["values", "在意的事", ""],
  ["taken_courses", "修過／正在修", ""],
  ["notes", "其他", ""],
];

const $ = (id) => document.getElementById(id);
let stages = [], holland = {}, statuses = [];
let state = loadState();
let busy = false;
let draft = null;          // 會談前的暫存
let recordId = null;       // 正在看哪一次的紀錄
let lastIntakeStep = null;

// ---------- storage ----------
function freshState() { return { stage: "senior_high", profile: null, sessions: [] }; }
function loadState() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY));
    if (s && Array.isArray(s.sessions)) return s;
  } catch (_) { /* private mode or corrupted: start fresh */ }
  return freshState();
}
function saveState() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (_) { /* ignore */ }
}

// ---------- helpers ----------
let mascotId = 0;
function mascotSVG() {
  const g = `mg${mascotId++}`;
  return `<svg viewBox="0 0 100 100" aria-hidden="true">
    <defs><radialGradient id="${g}" cx="35%" cy="30%" r="75%">
      <stop offset="0" stop-color="#ffbb88"/><stop offset="1" stop-color="#ff8a3d"/></radialGradient></defs>
    <path d="M50 5c24 0 44 17 44 43 0 26-20 47-45 47S6 75 6 49 26 5 50 5z" fill="url(#${g})"/>
    <path d="M29 47q6.5-8 13 0M58 47q6.5-8 13 0" stroke="#3b2f2a" stroke-width="4.5" fill="none" stroke-linecap="round"/>
    <path d="M41 61q9 9 18 0" stroke="#3b2f2a" stroke-width="4.5" fill="none" stroke-linecap="round"/>
    <ellipse cx="25" cy="60" rx="7" ry="4.5" fill="#f2897a" opacity=".5"/>
    <ellipse cx="75" cy="60" rx="7" ry="4.5" fill="#f2897a" opacity=".5"/>
  </svg>`;
}
function fillMascots(root = document) {
  root.querySelectorAll(".mascot:empty").forEach((el) => { el.innerHTML = mascotSVG(); });
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function md(text) {
  if (window.marked && window.DOMPurify) return DOMPurify.sanitize(marked.parse(text));
  return esc(text).replace(/\n/g, "<br>");
}
function stageInfo(id = state.stage) { return stages.find((s) => s.id === id) || stages[0]; }
function fmtDate(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
}
async function post(url, body) {
  let res, data;
  try {
    res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch (_) {
    throw new Error("連不上伺服器，請確認伺服器有在執行");
  }
  try { data = await res.json(); } catch (_) { throw new Error(`伺服器錯誤 ${res.status}`); }
  if (!res.ok || data.error) throw new Error(data.error || `伺服器錯誤 ${res.status}`);
  return data;
}
// inline error under a form part; empty message hides it
function showErr(id, msg) {
  const el = $(id);
  if (!el) return;
  el.textContent = msg || "";
  el.hidden = !msg;
}
const errBox = (id) => `<p class="err" id="${id}" role="alert" hidden></p>`;
function parseNum(v) {
  const s = String(v ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
}
function activeSession() { return state.sessions.find((s) => s.phase !== "done") || null; }
function doneSessions() { return state.sessions.filter((s) => s.phase === "done"); }
function allActions() { return state.sessions.flatMap((s) => s.actions || []); }
function pendingActions() { return allActions().filter((a) => PENDING.includes(a.status)); }
function findAction(id) { return allActions().find((a) => a.id === id); }
function addHistory(line) { state.profile.history.push(line); }
function addListItem(field, value, evidence) {
  const items = state.profile[field];
  if (items.includes(value)) return;
  items.push(value);
  const label = { strong_subjects: "擅長科目", weak_subjects: "較弱科目" }[field] || field;
  addHistory(`${label}：${value} ← 「${evidence}」`);
}
function setView(html) {
  const v = $("view");
  v.innerHTML = html;
  fillMascots(v);
  v.scrollTop = 0;
}

// ---------- routing ----------
function render() {
  const s = activeSession();
  if (s?.phase === "chat") renderSession(s);
  else if (s?.phase === "wrapup") renderWrapup(s);
  else if (s?.phase === "survey") renderSurvey(s);
  else if (recordId) renderRecord(state.sessions.find((x) => x.id === recordId));
  else if (draft) renderIntake();
  else renderLobby();
  renderStages();
  renderProfile();
}

// ---------- 首頁 ----------
function renderLobby() {
  const done = doneSessions();
  const n = state.sessions.length + 1;
  const pend = pendingActions();
  let html = `<div class="hero">
      <span class="mascot mascot-lg"></span>
      <h1>${done.length ? "歡迎回來！" : "嗨，我是小航"}</h1>
      <p>${done.length
        ? `這是我們的第 ${n} 次會談。${pend.length ? `上次你說要「${esc(pend[0].text)}」，等等跟我說說進度吧！` : "今天想聊什麼呢？"}`
        : "我會陪你聊聊喜歡的事、擅長的科目，一起找找適合你的方向。每次會談大約 15 分鐘，聊完會幫你整理一份紀錄。"}</p>
      <button class="btn primary big" id="startBtn" ${DEMO && state.sessions.length ? "disabled" : ""}>開始第 ${n} 次會談</button>
      ${DEMO && state.sessions.length ? `<p class="demo-hint">展示版只錄了一次會談。按右上角「全部清除」可以重新體驗。</p>` : ""}
      ${DEMO && !state.sessions.length ? `<p class="demo-hint">你將扮演示範學生「${esc(DEMO.persona.name)}」走一次完整的會談。</p>` : ""}
    </div>`;
  if (done.length) {
    html += `<h2 class="section-title">我的會談紀錄</h2><div class="record-grid">`;
    done.slice().reverse().forEach((s) => {
      const delta = (s.survey?.clarity_after ?? 0) - (s.clarity_before ?? 0);
      html += `<button class="record-card" data-id="${s.id}">
          <div class="rc-top"><b>第 ${s.n} 次</b><span class="muted small">${fmtDate(s.started)}</span></div>
          <div class="tags">${s.topics.slice(0, 2).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}${s.topics.length > 2 ? `<span class="tag">+${s.topics.length - 2}</span>` : ""}</div>
          <div class="small muted">方向清楚度 ${s.clarity_before ?? "?"} → ${s.survey?.clarity_after ?? "?"}
            ${delta > 0 ? `<span class="up">▲${delta}</span>` : ""}</div>
        </button>`;
    });
    html += `</div>`;
  }
  setView(html);
  $("startBtn").onclick = () => {
    draft = DEMO
      ? { step: 1, topics: [...DEMO.persona.topics], note: DEMO.persona.note, clarity: DEMO.persona.clarity_before, imports: [], editor: null }
      : { step: 1, topics: [], note: "", clarity: null, imports: [], editor: null };
    lastIntakeStep = null;
    render();
  };
  document.querySelectorAll(".record-card").forEach((b) => { b.onclick = () => { recordId = b.dataset.id; render(); }; });
}

// ---------- 會談前 ----------
function renderIntake() {
  const info = stageInfo();
  const steps = ["想聊什麼", "方向清楚度", "給小航看資料"];
  const enter = draft.step !== lastIntakeStep ? "enter" : "";
  lastIntakeStep = draft.step;
  let html = `<div class="intake">
    <ol class="stepper">${steps.map((t, i) => `<li class="${i + 1 === draft.step ? "on" : i + 1 < draft.step ? "done" : ""}"><span>${i + 1}</span>${t}</li>`).join("")}</ol>`;
  if (draft.step === 1) {
    html += `<div class="panel ${enter}">
      <h2>今天想聊什麼？</h2><p class="muted">可以選很多個，也可以都不選、直接寫下來。</p>
      ${DEMO ? `<p class="demo-hint">展示版：已依示範學生「${esc(DEMO.persona.name)}」選好，直接按下一步。</p>` : ""}
      <div class="topic-grid">${info.topics.map((t, i) => `<button class="topic ${draft.topics.includes(t) ? "on" : ""}" data-i="${i}">${esc(t)}</button>`).join("")}</div>
      <label class="field"><span>還有想補充的嗎？（選填）</span>
        <textarea id="noteInput" rows="2" maxlength="300" placeholder="例如：爸媽希望我讀醫科，但我比較喜歡畫畫" ${DEMO ? "readonly" : ""}>${esc(draft.note)}</textarea></label>
      ${errBox("err1")}
      <div class="nav"><button class="btn ghost" id="cancelIntake">取消</button><button class="btn primary" id="next1">下一步</button></div>
    </div>`;
  } else if (draft.step === 2) {
    html += `<div class="panel ${enter}">
      <h2>現在，你對自己想走的方向有多清楚？</h2><p class="muted">沒有對錯，照現在的感覺選就好。聊完之後會再問你一次。</p>
      ${DEMO ? `<p class="demo-hint">展示版：已依示範學生選好。</p>` : ""}
      ${clarityPicker("clarity", draft.clarity)}
      ${errBox("err2")}
      <div class="nav"><button class="btn ghost" id="back2">上一步</button><button class="btn primary" id="next2">下一步</button></div>
    </div>`;
  } else {
    html += `<div class="panel ${enter}">
      <h2>要不要先給小航看一些資料？</h2><p class="muted">可以跳過。拍照上傳的話，小航會先讀出來給你確認，確認後才會放進側寫。</p>
      <div class="import-grid">
        ${importCard("grades", "成績單", "知道你的強項和比較吃力的科目")}
        ${importCard("interest", "興趣測驗結果", "學校做過的興趣量表（R I A S E C）")}
      </div>
      <div id="editor"></div>
      <div class="nav"><button class="btn ghost" id="back3">上一步</button><button class="btn primary" id="startSession">開始會談</button></div>
      <p class="small muted center">${DEMO ? "展示版：按「用示範成績單」，會顯示 AI 對這張假成績單的真實辨識結果。" : "DEMO 建議用假的成績單測試：照片會送到 AI 服務處理。"}</p>
    </div>`;
  }
  html += `</div>`;
  setView(html);

  if (draft.step === 1) {
    document.querySelectorAll(".topic").forEach((b) => {
      b.onclick = () => {
        if (DEMO) return;
        const t = info.topics[+b.dataset.i];
        draft.topics = draft.topics.includes(t) ? draft.topics.filter((x) => x !== t) : [...draft.topics, t];
        b.classList.toggle("on");
        showErr("err1", "");
      };
    });
    $("noteInput").oninput = (e) => { draft.note = e.target.value; showErr("err1", ""); };
    $("cancelIntake").onclick = () => { draft = null; render(); };
    $("next1").onclick = () => {
      draft.note = draft.note.trim();
      if (!draft.topics.length && draft.note.length < 2) {
        showErr("err1", "請至少選一個議題，或在下面寫下你想聊的事。");
        return;
      }
      draft.step = 2; render();
    };
  } else if (draft.step === 2) {
    if (!DEMO) bindClarity("clarity", (v) => { draft.clarity = v; showErr("err2", ""); });
    $("back2").onclick = () => { draft.step = 1; render(); };
    $("next2").onclick = () => {
      if (!draft.clarity) { showErr("err2", "請選一個最接近你現在感覺的數字。"); return; }
      draft.step = 3; render();
    };
  } else {
    document.querySelectorAll("[data-import]").forEach((b) => {
      b.onclick = () => openImport(b.dataset.import, b.dataset.mode);
    });
    document.querySelectorAll("[data-demo-photo]").forEach((b) => {
      b.onclick = async () => {
        const blob = await (await fetch(DEMO.sampleImage)).blob();
        handlePhoto(b.dataset.demoPhoto, new File([blob], "sample-report.png", { type: blob.type || "image/png" }));
      };
    });
    renderEditor();
    $("back3").onclick = () => { draft.step = 2; draft.editor = null; render(); };
    $("startSession").onclick = startSession;
  }
}

function clarityPicker(name, value) {
  return `<div class="clarity" role="radiogroup">${CLARITY.map((label, i) => `
    <button type="button" class="clarity-opt ${value === i + 1 ? "on" : ""}" data-name="${name}" data-v="${i + 1}" role="radio" aria-checked="${value === i + 1}">
      <span class="face">${faceSVG(i + 1)}</span><b>${i + 1}</b><span>${label}</span></button>`).join("")}</div>`;
}
function bindClarity(name, onPick) {
  document.querySelectorAll(`.clarity-opt[data-name="${name}"]`).forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll(`.clarity-opt[data-name="${name}"]`).forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-checked", "false"); });
      b.classList.add("on"); b.setAttribute("aria-checked", "true");
      onPick(+b.dataset.v);
    };
  });
}

function importCard(kind, title, desc) {
  const done = draft.imports.some((x) => x.kind === kind);
  return `<div class="import-card ${done ? "done" : ""}">
    <div class="ic-icon">${done ? ICONS.done : ICONS[kind]}</div>
    <div><b>${title}</b><div class="small muted">${done ? "已加入側寫" : desc}</div></div>
    <div class="ic-actions">
      ${!DEMO ? `<label class="btn soft small">拍照上傳<input type="file" accept="image/*" hidden data-file="${kind}"></label>`
        : kind === "grades" ? `<button class="btn soft small" data-demo-photo="${kind}">用示範成績單</button>` : ""}
      <button class="btn ghost small" data-import="${kind}" data-mode="manual">手動輸入</button>
    </div></div>`;
}

// photo → shrink in the browser → /api/extract → editable table
document.addEventListener("change", (e) => {
  const kind = e.target.dataset?.file;
  if (!kind || !e.target.files?.[0]) return;
  const file = e.target.files[0];
  e.target.value = "";
  handlePhoto(kind, file);
});

async function handlePhoto(kind, file) {
  if (!file.type.startsWith("image/")) { draft.editor = { kind, error: "請選擇圖片檔（JPG 或 PNG）。" }; renderEditor(); return; }
  if (file.size > 15 * 1024 * 1024) { draft.editor = { kind, error: "圖片太大（超過 15 MB），請裁切後再上傳。" }; renderEditor(); return; }
  draft.editor = { kind, loading: true };
  renderEditor();
  try {
    const b64 = await shrinkImage(file);
    const data = await post("/api/extract", { kind, image_b64: b64, media_type: "image/jpeg" });
    const what = kind === "grades" ? "成績單" : "興趣測驗結果";
    if (!data.data.readable) throw new Error(`看不太出來這是${what}，可以重拍或改用手動輸入。`);
    if (kind === "grades" && !data.data.items.length) throw new Error("沒有讀到任何科目和分數，可以重拍或改用手動輸入。");
    if (kind === "interest" && !Object.values(data.data.scores).some((v) => v > 0)) throw new Error("沒有讀到興趣分數，可以重拍或改用手動輸入。");
    if (kind === "grades") {
      draft.editor = { kind, source: "成績單照片", note: data.data.notes,
        rows: data.data.items.map((it) => ({ subject: it.subject, score: it.score,
          tag: data.strong.includes(it.subject) ? "strong" : data.weak.includes(it.subject) ? "weak" : "" })) };
    } else {
      draft.editor = { kind, source: "興趣測驗照片", note: data.data.notes, scores: data.data.scores, max: data.data.scale_max };
    }
    draft.editor.preview = URL.createObjectURL(file);
  } catch (err) {
    draft.editor = { kind, error: err.message };
  }
  renderEditor();
}

function shrinkImage(file, maxSide = 1600) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, maxSide / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(img.src);
      resolve(c.toDataURL("image/jpeg", 0.85).split(",")[1]);
    };
    img.onerror = () => reject(new Error("讀不到這張圖片。iPhone 的 HEIC 照片請改成 JPG，或用截圖上傳。"));
    img.src = URL.createObjectURL(file);
  });
}

function openImport(kind, mode) {
  if (mode !== "manual") return;
  draft.editor = kind === "grades"
    ? { kind, source: "手動輸入", rows: stageInfo().subjects.map((s) => ({ subject: s, score: "", tag: "" })) }
    : { kind, source: "手動輸入", scores: { R: "", I: "", A: "", S: "", E: "", C: "" }, max: 100 };
  renderEditor();
}

function renderEditor() {
  const box = $("editor");
  if (!box) return;
  const ed = draft.editor;
  if (!ed) { box.innerHTML = ""; return; }
  if (ed.loading) { box.innerHTML = `<div class="editor"><div class="typing"><span class="dots"><i></i><i></i><i></i></span>小航正在讀圖片…</div></div>`; return; }
  if (ed.error) { box.innerHTML = `<div class="editor error-box" role="alert">${esc(ed.error)} <button class="btn ghost small" id="edClose">關閉</button></div>`; $("edClose").onclick = () => { draft.editor = null; renderEditor(); }; return; }

  const bad = ed.check?.rowErrors || {};
  let html = `<div class="editor"><div class="ed-head"><b>${ed.kind === "grades" ? "確認成績" : "確認興趣測驗分數"}</b><span class="small muted">來源：${esc(ed.source)}</span></div>`;
  if (ed.preview) html += `<img class="ed-preview" src="${ed.preview}" alt="上傳的照片，對照用">`;
  if (ed.note) html += `<p class="small muted">小航的備註：${esc(ed.note)}</p>`;
  if (ed.kind === "grades") {
    html += `<p class="small muted">分數不對可以直接改，沒有分數的科目會略過。「擅長／吃力」是小航依你自己的平均建議的，分數高不一定代表喜歡，請照你的感覺調整。</p>
      <table class="grades"><thead><tr><th>科目</th><th>分數（0–100）</th><th>你覺得</th><th></th></tr></thead><tbody>
      ${ed.rows.map((r, i) => `<tr class="${bad[i] ? "invalid" : ""}">
        <td><input data-row="${i}" data-k="subject" maxlength="20" value="${esc(r.subject)}" aria-label="科目"></td>
        <td><input data-row="${i}" data-k="score" inputmode="decimal" maxlength="5" value="${esc(r.score)}" aria-label="分數"></td>
        <td><div class="seg">${[["strong", "擅長"], ["", "普通"], ["weak", "吃力"]].map(([v, l]) => `<button type="button" class="${r.tag === v ? "on" : ""}" data-row="${i}" data-tag="${v}">${l}</button>`).join("")}</div></td>
        <td><button type="button" class="x" data-del="${i}" aria-label="刪除這一列">×</button></td></tr>
        ${bad[i] ? `<tr class="row-err"><td colspan="4">${esc(bad[i])}</td></tr>` : ""}`).join("")}
      </tbody></table>
      <div class="ed-tools"><button class="btn ghost small" id="addRow">＋ 新增科目</button><button class="btn soft small" id="suggest">小航建議強弱科</button></div>`;
  } else {
    html += `<div class="interest-inputs">${HOLLAND_ORDER.map((k) => `<label class="${bad[k] ? "invalid" : ""}"><span style="color:var(--h-${k})">${esc(holland[k] || k)}</span>
        <input inputmode="decimal" maxlength="6" data-h="${k}" value="${esc(ed.scores[k])}"></label>`).join("")}
      <label class="${bad.max ? "invalid" : ""}"><span>滿分</span><input inputmode="decimal" maxlength="6" id="hMax" value="${esc(ed.max)}"></label></div>
      <p class="small muted">百分等級的滿分是 100；空白的類型會略過。換算後會直接畫進興趣地圖。</p>`;
  }
  html += `${errBox("edErr")}<div class="nav"><button class="btn ghost" id="edCancel">取消</button><button class="btn primary" id="edOk">確認加入側寫</button></div></div>`;
  box.innerHTML = html;
  if (ed.check?.message) showErr("edErr", ed.check.message);

  box.querySelectorAll("input[data-row]").forEach((inp) => {
    inp.oninput = () => { ed.rows[+inp.dataset.row][inp.dataset.k] = inp.value; };
  });
  box.querySelectorAll("button[data-tag]").forEach((b) => {
    b.onclick = () => { ed.rows[+b.dataset.row].tag = b.dataset.tag; ed.check = null; renderEditor(); };
  });
  box.querySelectorAll("button[data-del]").forEach((b) => {
    b.onclick = () => { ed.rows.splice(+b.dataset.del, 1); ed.check = null; renderEditor(); };
  });
  box.querySelectorAll("input[data-h]").forEach((inp) => { inp.oninput = () => { ed.scores[inp.dataset.h] = inp.value; }; });
  if ($("hMax")) $("hMax").oninput = (e) => { ed.max = e.target.value; };
  if ($("addRow")) $("addRow").onclick = () => {
    if (ed.rows.length >= 30) { ed.check = { message: "最多 30 個科目。" }; renderEditor(); return; }
    ed.rows.push({ subject: "", score: "", tag: "" }); ed.check = null; renderEditor();
  };
  if ($("suggest")) $("suggest").onclick = async () => {
    const check = checkGrades(ed.rows);
    ed.check = check;
    if (check.message) { renderEditor(); return; }
    try {
      const s = await post("/api/strengths", { grades: Object.fromEntries(check.rows.map((r) => [r.subject, r.score])) });
      // only rows that actually have a score get a suggestion (a blank row with the same name must stay untagged)
      ed.rows.forEach((r) => {
        const n = String(r.subject).trim(), score = parseNum(r.score);
        if (score === null || Number.isNaN(score)) return;
        r.tag = s.strong.includes(n) ? "strong" : s.weak.includes(n) ? "weak" : "";
      });
      if (!s.strong.length && !s.weak.length) ed.check = { message: "你各科分數差不多，小航看不出明顯的強弱，可以照你的感覺自己選。" };
    } catch (err) { ed.check = { message: err.message }; }
    renderEditor();
  };
  $("edCancel").onclick = () => { draft.editor = null; renderEditor(); };
  $("edOk").onclick = () => confirmImport(ed);
}

// Returns {rows: valid rows, rowErrors: {index: msg}, message}. Empty message = OK.
function checkGrades(rows) {
  const rowErrors = {}, valid = [], seen = new Set();
  rows.forEach((r, i) => {
    const subject = String(r.subject ?? "").trim();
    const score = parseNum(r.score);
    if (!subject && score === null) { if (r.tag) rowErrors[i] = "這一列是空的，不能標擅長或吃力"; return; }
    if (!subject) { rowErrors[i] = "請填科目名稱"; return; }
    if (score === null) { if (r.tag) rowErrors[i] = `「${subject}」要填分數才能標擅長或吃力`; return; }
    if (Number.isNaN(score)) { rowErrors[i] = `「${subject}」的分數要是數字`; return; }
    if (score < 0 || score > 100) { rowErrors[i] = `「${subject}」的分數要在 0 到 100 之間`; return; }
    if (seen.has(subject)) { rowErrors[i] = `「${subject}」重複了，請刪掉一列`; return; }
    seen.add(subject);
    valid.push({ subject, score, tag: r.tag });
  });
  let message = "";
  if (Object.keys(rowErrors).length) message = "有幾列需要修正（標紅色的地方）。";
  else if (!valid.length) message = "至少要填一個科目的分數。";
  return { rows: valid, rowErrors, message };
}

function checkInterest(ed) {
  const rowErrors = {}, raw = {};
  const max = parseNum(ed.max);
  if (max === null || Number.isNaN(max) || max <= 0 || max > 1000) rowErrors.max = "滿分要是 1 到 1000 之間的數字";
  HOLLAND_ORDER.forEach((k) => {
    const v = parseNum(ed.scores[k]);
    if (v === null) return;
    if (Number.isNaN(v) || v < 0) { rowErrors[k] = "要是 0 以上的數字"; return; }
    if (!rowErrors.max && v > max) { rowErrors[k] = "不能超過滿分"; return; }
    raw[k] = v;
  });
  let message = "";
  const names = Object.keys(rowErrors).map((k) => (k === "max" ? "滿分" : holland[k]) + "：" + rowErrors[k]);
  if (names.length) message = names.join("；");
  else if (!Object.keys(raw).length) message = "至少要填一個類型的分數。";
  return { raw, max, rowErrors, message };
}

function confirmImport(ed) {
  if (ed.kind === "grades") {
    const check = checkGrades(ed.rows);
    ed.check = check;
    if (check.message) { renderEditor(); return; }
    check.rows.forEach((r) => {
      if (r.tag === "strong") addListItem("strong_subjects", r.subject, `${ed.source}：${r.subject} ${r.score}`);
      if (r.tag === "weak") addListItem("weak_subjects", r.subject, `${ed.source}：${r.subject} ${r.score}`);
    });
    draft.imports = draft.imports.filter((x) => x.kind !== "grades").concat({ kind: "grades", source: ed.source, rows: check.rows });
  } else {
    const check = checkInterest(ed);
    ed.check = check;
    if (check.message) { renderEditor(); return; }
    Object.entries(check.raw).forEach(([k, v]) => {
      const score = Math.round(Math.max(0, Math.min(1, v / check.max)) * 100) / 100;   // same rule as planner/session.py
      const t = state.profile.interests[k];
      t.score = score; t.evidence.push(`${ed.source}：${k} ${v}/${check.max}`);
      addHistory(`興趣.${holland[k]}：${score.toFixed(1)} ← 「${ed.source}：${v}/${check.max}」`);
    });
    draft.imports = draft.imports.filter((x) => x.kind !== "interest").concat({ kind: "interest", source: ed.source, raw: check.raw, max: check.max });
  }
  draft.editor = null;
  saveState();
  renderIntake();
  renderProfile();
}

// ---------- 會談 ----------
function sessionContext(s) {
  return { topics: s.topics, note: s.note, clarity_before: s.clarity_before, session_number: s.n,
           previous_actions: pendingActions().map(({ id, text, status, note }) => ({ id, text, status, note })) };
}

async function startSession() {
  const s = { id: Date.now().toString(36), n: state.sessions.length + 1, started: new Date().toISOString(),
              stage: state.stage, topics: draft.topics, note: draft.note.trim(), clarity_before: draft.clarity,
              imports: draft.imports, chat: [], phase: "chat", actions: [], summary: null, survey: null };
  state.sessions.push(s);
  draft = null;
  saveState();
  render();
  await kickoff(s);
}

async function kickoff(s) {
  busy = true; renderSession(s); showTyping();
  try {
    const data = await post("/api/chat", { kickoff: true, stage: s.stage, profile: state.profile, history: [], session: sessionContext(s) });
    s.chat.push({ role: "user", content: data.user_message, hidden: true }, { role: "assistant", content: data.reply });
    applyTurn(data);
  } catch (err) {
    s.kickoffError = err.message;
  }
  busy = false; saveState(); render();
}

function renderSession(s) {
  const visible = s.chat.filter((m) => !m.hidden);
  let html = `<div class="session-bar">
      <div><b>第 ${s.n} 次會談</b><div class="tags">${s.topics.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div></div>
      <button class="btn ghost" id="endBtn" ${busy || !visible.length ? "disabled" : ""}>結束會談</button>
    </div>
    <div class="messages" id="messages">`;
  const seen = shownMessages[s.id] ?? visible.length;   // first paint after a reload: nothing animates
  visible.forEach((m, i) => { html += messageHTML(m.role, m.content, i >= seen ? "new" : ""); });
  shownMessages[s.id] = visible.length;
  if (!visible.length && !busy) {   // kickoff failed, or the page was closed while it was running
    html += messageHTML("assistant", s.kickoffError ? `哎呀，會談沒有順利開始（${s.kickoffError}）。` : "會談還沒開始。", s.kickoffError ? "error" : "")
         + `<div class="center"><button class="btn primary" id="retryKick">開始</button></div>`;
  }
  html += `</div>
    <div class="composer">
      ${DEMO ? demoSayHTML(s) : ""}
      <form class="input-row" id="form">
        <textarea id="input" rows="1" maxlength="500" placeholder="${DEMO ? "展示版：請點上面的句子送出" : "說說你的想法，什麼都可以…"}" aria-label="輸入訊息" ${DEMO ? "disabled" : ""}></textarea>
        <button type="submit" class="send" id="sendBtn" aria-label="送出" ${busy ? "disabled" : ""}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 12l16-8-6 16-2.5-6.5L4 12z" fill="currentColor"/></svg>
        </button>
      </form>
      <p class="footnote">聊完了就按右上角「結束會談」，小航會幫你整理紀錄。重要的決定，記得和老師、家人一起討論。</p>
    </div>`;
  const v = $("view");
  v.innerHTML = `<div class="session">${html}</div>`;
  fillMascots(v);
  const box = $("messages");
  box.scrollTop = box.scrollHeight;

  $("form").onsubmit = (e) => { e.preventDefault(); send(s, $("input").value); };
  $("input").oninput = autosize;
  $("input").onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(s, $("input").value); }
  };
  $("endBtn").onclick = () => endSession(s);
  if ($("demoSay")) $("demoSay").onclick = () => send(s, $("demoSay").dataset.line);
  if ($("retryKick")) $("retryKick").onclick = () => { delete s.kickoffError; kickoff(s); };
  if (!busy && !DEMO) $("input").focus();
}

function demoSayHTML(s) {
  const sent = s.chat.filter((m) => m.role === "user" && !m.hidden).length;
  const line = DEMO.persona.lines[sent];
  if (busy || !s.chat.length) return "";
  if (!line) return `<p class="demo-say small muted">示範對話到這裡結束了，按右上角「結束會談」看看會談整理。</p>`;
  return `<div class="demo-say"><span class="small muted">點一下，替${esc(DEMO.persona.name)}說：</span>
    <button type="button" class="chip" id="demoSay" data-line="${esc(line)}">${esc(line)}</button></div>`;
}

function messageHTML(role, content, extra = "") {
  const user = role === "user";
  const body = user ? esc(content).replace(/\n/g, "<br>") : md(content);
  return `<div class="msg ${user ? "user" : "bot"} ${extra}">${user ? "" : `<span class="mascot mascot-sm"></span>`}<div class="bubble">${body}</div></div>`;
}

function showTyping() {
  const box = $("messages");
  if (!box) return;
  const el = document.createElement("div");
  el.className = "msg bot"; el.id = "typing";
  el.innerHTML = `<span class="mascot mascot-sm"></span><div class="bubble typing"><span class="dots"><i></i><i></i><i></i></span><span id="typingText">${THINKING[0]}</span></div>`;
  box.appendChild(el);
  fillMascots(el);
  box.scrollTop = box.scrollHeight;
  let i = 0;
  el.dataset.timer = setInterval(() => { const t = $("typingText"); if (t) t.textContent = THINKING[++i % THINKING.length]; }, 2600);
}

async function send(s, text) {
  text = (text || "").trim();
  if (!text || busy) return;
  const history = s.chat.map(({ role, content }) => ({ role, content }));
  s.chat.push({ role: "user", content: text });
  busy = true; renderSession(s); showTyping();
  try {
    const data = await post("/api/chat", { message: text, stage: s.stage, profile: state.profile, history, session: sessionContext(s) });
    s.chat.push({ role: "assistant", content: data.reply });
    applyTurn(data);
    busy = false; saveState(); render();
  } catch (err) {
    s.chat.pop();                       // don't keep a question that never got an answer
    busy = false; render();
    $("messages").insertAdjacentHTML("beforeend", messageHTML("assistant", `哎呀，剛剛沒有連上（${err.message}）。訊息已經放回輸入框，再送一次試試看。`, "error"));
    fillMascots($("messages"));
    $("input").value = text; autosize();
  }
}

function applyTurn(data) {
  const before = state.profile.history.length;
  state.profile = data.profile;
  (data.action_updates || []).forEach((u) => {
    const a = findAction(u.id);
    if (a) { a.status = u.status; a.note = u.note; }
  });
  lastHistoryLength = before;
  renderTrace(data);
}
let lastHistoryLength = null;
const shownMessages = {};   // session id → how many messages are already on screen

// ---------- 結束：整理 + 學生寫下一步 ----------
async function endSession(s) {
  if (busy || !confirm("要結束這次會談了嗎？\n結束後小航會整理紀錄，接著請你寫下一步和自評表。")) return;
  s.phase = "wrapup"; s.ended = new Date().toISOString();
  s.profile_snapshot = JSON.parse(JSON.stringify(state.profile));
  saveState(); render();
  await loadSummary(s);
}

async function loadSummary(s) {
  s.summaryError = null; busy = true; renderWrapup(s);
  try {
    const data = await post("/api/summary", { chat: s.chat, profile: state.profile, topics: s.topics });
    s.summary = data.summary;
  } catch (err) { s.summaryError = err.message; }
  busy = false; saveState(); renderWrapup(s);
}

function renderWrapup(s) {
  const sum = s.summary;
  let html = `<div class="panel wide">
    <div class="panel-head"><span class="mascot mascot-sm"></span><h2>今天的會談整理</h2></div>`;
  if (!sum && busy) html += `<div class="typing"><span class="dots"><i></i><i></i><i></i></span>小航正在整理今天聊的內容…</div>`;
  else if (!sum) html += `<p class="error-box">整理失敗（${esc(s.summaryError || "")}）<button class="btn ghost small" id="retrySum">再試一次</button></p>`;
  else html += listBlock("今天聊了", sum.talked_about) + listBlock("你的發現", sum.discoveries);
  html += `</div>
    <div class="panel wide">
      <h2>你的下一步</h2>
      <p class="muted">寫下 1–3 件<b>你自己</b>想做的事。小航不會幫你決定，下次會談會關心你做得怎麼樣。</p>
      ${[0, 1, 2].map((i) => `<input class="action-input" data-i="${i}" maxlength="80" value="${esc(s.actionDrafts?.[i] || "")}"
          placeholder="${["例如：寒假前查好兩個資訊營", "例如：問表哥大學在學什麼", "例如：這週末上網看三個科系介紹"][i]}">`).join("")}
      ${errBox("actErr")}
      <div class="nav"><span></span><button class="btn primary" id="toSurvey" ${busy ? "disabled" : ""}>下一步：填自評表</button></div>
    </div>`;
  setView(html);
  document.querySelectorAll(".action-input").forEach((inp) => {
    inp.oninput = () => {
      s.actionDrafts = s.actionDrafts || []; s.actionDrafts[+inp.dataset.i] = inp.value;
      inp.classList.remove("invalid"); showErr("actErr", ""); saveState();
    };
  });
  if ($("retrySum")) $("retrySum").onclick = () => loadSummary(s);
  $("toSurvey").onclick = () => {
    const inputs = [...document.querySelectorAll(".action-input")];
    const texts = [], problems = [];
    inputs.forEach((inp, i) => {
      const t = inp.value.trim();
      inp.classList.remove("invalid");
      if (!t) return;
      if (t.length < 2) { problems.push(`第 ${i + 1} 個太短了，多寫幾個字`); inp.classList.add("invalid"); return; }
      if (texts.includes(t)) { problems.push(`第 ${i + 1} 個跟前面重複了`); inp.classList.add("invalid"); return; }
      texts.push(t);
    });
    if (problems.length) { showErr("actErr", problems.join("；")); return; }
    if (!texts.length && !confirm("確定這次不寫下一步嗎？")) return;
    s.actions = texts.map((text, i) => ({ id: `${s.id}-${i + 1}`, text, status: "還沒開始", note: "" }));
    s.phase = "survey";
    saveState(); render();
  };
}

function listBlock(title, items) {
  if (!items?.length) return "";
  return `<h3 class="block-title">${title}</h3><ul class="nice">${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

// ---------- 自評表（填完才能開下一次） ----------
function renderSurvey(s) {
  const sv = s.surveyDraft || (s.surveyDraft = { clarity_after: null, helpful: [], helpful_other: "", confidence: null, issues: "", reflection: "" });
  const hasActions = s.actions.length > 0;
  let html = `<div class="panel wide survey">
    <div class="panel-head"><span class="mascot mascot-sm"></span><div><h2>今天聊得怎麼樣？</h2>
      <p class="muted">花 1 分鐘回答一下，填完才能開始下一次會談喔。</p></div></div>
    <div class="q"><div class="q-title">1. 聊完之後，你對自己想走的方向有多清楚？</div>
      <p class="small muted">會談前你選的是 ${s.clarity_before}（${CLARITY[s.clarity_before - 1]}）</p>
      ${clarityPicker("after", sv.clarity_after)}${errBox("q1Err")}</div>
    <div class="q"><div class="q-title">2. 今天最有幫助的是？（可以複選）</div>
      <div class="checks">${HELPFUL.map((h) => `<label class="check"><input type="checkbox" value="${h}" ${sv.helpful.includes(h) ? "checked" : ""}> ${h}</label>`).join("")}</div>
      <input class="text-in" id="helpfulOther" maxlength="100" placeholder="其他（選填）" value="${esc(sv.helpful_other)}"></div>`;
  if (hasActions) {
    html += `<div class="q"><div class="q-title">3. 你寫的下一步，有信心做到嗎？</div>
      <ul class="nice small">${s.actions.map((a) => `<li>${esc(a.text)}</li>`).join("")}</ul>
      <div class="scale">${[1, 2, 3, 4, 5].map((v) => `<button type="button" class="scale-opt ${sv.confidence === v ? "on" : ""}" data-v="${v}">${v}</button>`).join("")}</div>
      <div class="scale-labels small muted"><span>沒什麼信心</span><span>很有信心</span></div>${errBox("q3Err")}</div>`;
  }
  html += `<div class="q"><div class="q-title">${hasActions ? 4 : 3}. 小航有沒有哪裡說錯，或讓你不舒服？（選填）</div>
      <textarea class="text-in" id="issues" rows="2" maxlength="300">${esc(sv.issues)}</textarea></div>
    <div class="q"><div class="q-title">${hasActions ? 5 : 4}. 用一句話寫下：今天你更了解自己什麼？</div>
      <textarea class="text-in" id="reflection" rows="2" maxlength="200" placeholder="例如：我發現我喜歡的是解決問題，不是電腦本身">${esc(sv.reflection)}</textarea>${errBox("q5Err")}</div>
    <div class="nav"><span class="small muted" id="surveyMsg"></span><button class="btn primary" id="submitSurvey">送出，看會談紀錄</button></div>
  </div>`;
  setView(html);
  bindClarity("after", (v) => { sv.clarity_after = v; showErr("q1Err", ""); saveState(); });
  document.querySelectorAll(".checks input").forEach((c) => {
    c.onchange = () => { sv.helpful = [...document.querySelectorAll(".checks input:checked")].map((x) => x.value); saveState(); };
  });
  document.querySelectorAll(".scale-opt").forEach((b) => {
    b.onclick = () => { sv.confidence = +b.dataset.v; document.querySelectorAll(".scale-opt").forEach((x) => x.classList.toggle("on", x === b)); showErr("q3Err", ""); saveState(); };
  });
  $("helpfulOther").oninput = (e) => { sv.helpful_other = e.target.value; saveState(); };
  $("issues").oninput = (e) => { sv.issues = e.target.value; saveState(); };
  $("reflection").oninput = (e) => { sv.reflection = e.target.value; showErr("q5Err", ""); saveState(); };
  $("submitSurvey").onclick = () => {
    const errs = [];
    if (!sv.clarity_after) { showErr("q1Err", "請選一個數字"); errs.push("q1Err"); }
    if (hasActions && !sv.confidence) { showErr("q3Err", "請選一個數字"); errs.push("q3Err"); }
    const refl = sv.reflection.trim();
    if (refl.length < 4) { showErr("q5Err", refl ? "多寫幾個字吧（至少 4 個字）" : "這題要寫，一句話就好"); errs.push("q5Err"); }
    if (errs.length) {
      $("surveyMsg").textContent = `還有 ${errs.length} 題要完成`;
      $(errs[0]).closest(".q").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    s.survey = { ...sv, reflection: refl, helpful_other: sv.helpful_other.trim(), issues: sv.issues.trim(), submitted: new Date().toISOString() };
    delete s.surveyDraft;
    s.phase = "done";
    recordId = s.id;
    saveState(); render();
  };
}

// ---------- 會談紀錄（可匯出 PDF／圖片） ----------
function renderRecord(s) {
  if (!s) { recordId = null; renderLobby(); return; }
  const p = s.profile_snapshot || state.profile;
  const sum = s.summary || { talked_about: [], discoveries: [], questions_for_teacher: [] };
  const top = HOLLAND_ORDER.map((k) => [k, p.interests[k].score]).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 2);
  const before = s.clarity_before, after = s.survey?.clarity_after;
  const dots = (v) => [1, 2, 3, 4, 5].map((i) => `<i class="${i <= v ? "on" : ""}"></i>`).join("");
  const html = `<div class="record-actions no-print">
      <button class="btn ghost" id="backHome">← 回首頁</button>
      <span><button class="btn soft" id="savePdf">下載 PDF</button> <button class="btn soft" id="saveImg">下載圖片</button></span>
    </div>
    <article class="record" id="record">
      <header class="rec-head"><span class="mascot mascot-sm"></span>
        <div><h1>小航會談紀錄</h1><div class="muted small">第 ${s.n} 次會談・${fmtDate(s.started)}・${esc(stageInfo(s.stage)?.name || "")}</div></div></header>
      <section><h3>今天想聊</h3><div class="tags">${s.topics.map((t) => `<span class="tag">${esc(t)}</span>`).join("") || "<span class='muted'>沒有選議題</span>"}</div>
        ${s.note ? `<p class="small">補充：${esc(s.note)}</p>` : ""}</section>
      <section><h3>方向清楚度</h3>
        <div class="clarity-row"><span>會談前</span><span class="dots5">${dots(before)}</span><b>${before}</b></div>
        <div class="clarity-row"><span>會談後</span><span class="dots5">${dots(after)}</span><b>${after ?? "-"}</b>
          ${after - before > 0 ? `<span class="up">▲ 進步 ${after - before}</span>` : ""}</div></section>
      ${sum.talked_about.length ? `<section><h3>今天聊了</h3><ul class="nice">${sum.talked_about.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>` : ""}
      ${sum.discoveries.length ? `<section><h3>你的發現</h3><ul class="nice">${sum.discoveries.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>` : ""}
      <section><h3>你的下一步</h3>${s.actions.length ? `<ul class="nice">${s.actions.map((a) => `<li>${esc(a.text)} <span class="pill">${esc(a.status)}</span></li>`).join("")}</ul>` : "<p class='muted'>這次沒有寫下一步</p>"}</section>
      ${sum.questions_for_teacher.length ? `<section><h3>可以帶去問老師的問題</h3><ul class="nice">${sum.questions_for_teacher.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>` : ""}
      <section><h3>側寫重點</h3><div class="facts-inline">
        <div><span class="muted small">興趣前兩名</span><b>${top.map(([k, v]) => `${esc(holland[k])} ${v.toFixed(1)}`).join("、") || "還不清楚"}</b></div>
        <div><span class="muted small">擅長</span><b>${esc(p.strong_subjects.join("、")) || "—"}</b></div>
        <div><span class="muted small">目標</span><b>${esc(p.goals.join("、")) || "—"}</b></div></div></section>
      ${s.survey?.reflection ? `<section><h3>你的反思</h3><blockquote>${esc(s.survey.reflection)}</blockquote></section>` : ""}
      <footer class="small muted">本紀錄由 AI 學習規劃助理「小航」整理，僅供參考。重要決定請和課諮師、輔導老師、家人討論。</footer>
    </article>`;
  setView(html);
  $("backHome").onclick = () => { recordId = null; render(); };
  $("savePdf").onclick = () => window.print();
  $("saveImg").onclick = async () => {
    if (!window.html2canvas) { alert("圖片功能需要網路載入元件，請改用下載 PDF。"); return; }
    const canvas = await html2canvas($("record"), { scale: 2, backgroundColor: "#fffaf4" });
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `小航會談紀錄-第${s.n}次.png`;
    a.click();
  };
}

// ---------- 側寫面板 ----------
function renderProfile() {
  const p = state.profile;
  if (!p) return;
  renderRadar(p);
  renderFacts(p);
  renderActionsPanel();
  renderWhy(p, lastHistoryLength);
  lastHistoryLength = null;
  const info = stageInfo();
  $("disclaimer").textContent = info ? `${info.name}｜${info.disclaimer}` : "";
}

function renderRadar(p) {
  const cx = 150, cy = 136, R = 92;
  const pt = (i, r) => { const a = (-90 + i * 60) * Math.PI / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
  const poly = (r) => HOLLAND_ORDER.map((_, i) => pt(i, r).join(",")).join(" ");
  let svg = "";
  [0.25, 0.5, 0.75, 1].forEach((f) => { svg += `<polygon class="ring" points="${poly(R * f)}"/>`; });
  HOLLAND_ORDER.forEach((_, i) => { const [x, y] = pt(i, R); svg += `<line class="axis" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`; });
  const scores = HOLLAND_ORDER.map((k) => p.interests?.[k]?.score || 0);
  svg += `<polygon class="area" points="${scores.map((s, i) => pt(i, Math.max(R * s, 3)).join(",")).join(" ")}"/>`;
  HOLLAND_ORDER.forEach((k, i) => {
    const color = `var(--h-${k})`;
    const [dx, dy] = pt(i, Math.max(R * scores[i], 3));
    if (scores[i] > 0) svg += `<circle class="dot" cx="${dx}" cy="${dy}" r="5" fill="${color}"/>`;
    const [lx, ly] = pt(i, R + 22);
    const anchor = Math.abs(lx - cx) < 5 ? "middle" : lx > cx ? "start" : "end";
    svg += `<text x="${lx}" y="${ly}" text-anchor="${anchor}" dominant-baseline="middle" fill="${color}">${(holland[k] || k).replace("型", "")}`
         + `<tspan class="score" dx="4">${scores[i] ? scores[i].toFixed(1) : ""}</tspan></text>`;
  });
  $("radar").innerHTML = svg;
  $("radarHint").textContent = scores.some((s) => s > 0)
    ? "越往外，代表你越喜歡這類活動。數值是小航目前的猜測，可以直接跟它說哪裡不對。"
    : "聊得越多，地圖會越清楚。";
}

function renderFacts(p) {
  let html = "";
  if (p.grade) html += `<div class="fact"><div class="fact-label">年級</div><div class="tags"><span class="tag">${esc(p.grade)}</span></div></div>`;
  LIST_LABELS.forEach(([field, label, cls]) => {
    const items = p[field] || [];
    if (!items.length) return;
    html += `<div class="fact"><div class="fact-label">${label}</div><div class="tags">${items.map((v) => `<span class="tag ${cls}">${esc(v)}</span>`).join("")}</div></div>`;
  });
  $("facts").innerHTML = html || `<p class="empty">還不認識你，先聊聊吧！</p>`;
}

function renderActionsPanel() {
  const acts = allActions();
  if (!acts.length) { $("actionsPanel").innerHTML = `<p class="empty">會談結束時，你可以寫下自己想做的事。</p>`; return; }
  $("actionsPanel").innerHTML = `<ul class="acts">${acts.slice(-6).reverse().map((a) => `
    <li><span>${esc(a.text)}${a.note ? `<span class="small muted d-block">${esc(a.note)}</span>` : ""}</span>
      <button class="pill st-${statuses.indexOf(a.status)}" data-act="${esc(a.id)}" title="點一下切換狀態">${esc(a.status)}</button></li>`).join("")}</ul>`;
  document.querySelectorAll("[data-act]").forEach((b) => {
    b.onclick = () => {
      const a = findAction(b.dataset.act);
      a.status = statuses[(statuses.indexOf(a.status) + 1) % statuses.length];
      saveState(); renderActionsPanel();
    };
  });
}

function renderWhy(p, previousLength) {
  const hist = p.history || [];
  if (!hist.length) { $("why").innerHTML = `<li class="empty">小航每記下一件事，都會附上你說過的話。</li>`; return; }
  const start = Math.max(0, hist.length - 12);
  $("why").innerHTML = hist.slice(start).map((line, j) => {
    const [what, quote] = line.split(" ← ");
    const fresh = previousLength !== null && start + j >= previousLength ? "fresh" : "";
    return `<li class="${fresh}"><div class="what">${esc(what.replace("興趣.", "興趣・"))}</div>${quote ? `<div class="quote">${esc(quote)}</div>` : ""}</li>`;
  }).reverse().join("");
}

function renderTrace(data) {
  const calls = data.trace?.length ? data.trace.map((t) => `<li><code>${esc(t)}</code></li>`).join("") : "<li>沒有呼叫工具</li>";
  $("trace").innerHTML = `<ul>${calls}</ul>${data.seconds} 秒・US$${data.usd}`;
}

// ---------- 教育階段切換（只能在首頁切） ----------
function renderStages() {
  const locked = !!activeSession() || !!draft || !!DEMO;
  $("stageSwitch").innerHTML = "";
  stages.forEach((st) => {
    const b = document.createElement("button");
    b.type = "button"; b.role = "tab";
    b.textContent = st.id === "senior_high" ? "高中" : st.id === "junior_high" ? "國中" : st.name;
    b.title = DEMO ? "展示版固定為示範學生的教育階段" : locked ? "會談進行中不能切換" : st.decisions;
    b.disabled = locked && st.id !== state.stage;
    b.setAttribute("aria-selected", String(st.id === state.stage));
    b.onclick = () => {
      if (locked || st.id === state.stage) return;
      state.stage = st.id; state.profile.stage = st.id;
      saveState(); render();
    };
    $("stageSwitch").appendChild(b);
  });
}

// ---------- misc ----------
function autosize() {
  const t = $("input");
  if (!t) return;
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 160) + "px";
}
function toggleProfile(open) {
  $("profile").classList.toggle("open", open);
  $("scrim").classList.toggle("open", open);
}

async function init() {
  fillMascots();
  $("homeBtn").onclick = () => { if (!activeSession()) { draft = null; recordId = null; render(); } };
  $("resetBtn").onclick = async () => {
    if (busy || !confirm("要清除所有會談紀錄和側寫嗎？這個動作不能復原。")) return;
    const stage = state.stage;
    state = freshState(); state.stage = stage;
    state.profile = await (await fetch(`/api/profile/new?stage=${stage}`)).json();
    draft = null; recordId = null;
    saveState(); render();
    $("trace").textContent = "還沒有對話。";
  };
  $("openProfile").onclick = () => toggleProfile(true);
  $("closeProfile").onclick = () => toggleProfile(false);
  $("scrim").onclick = () => toggleProfile(false);

  try {
    const data = await (await fetch("/api/stages")).json();
    stages = data.stages; holland = data.holland; statuses = data.action_statuses;
  } catch (_) {
    $("view").innerHTML = `<p class="error-box">連不上伺服器，請確認 python -m planner.app 有在執行。</p>`;
    return;
  }
  if (DEMO) state.stage = DEMO.persona.stage;
  if (!stages.some((s) => s.id === state.stage)) state.stage = stages[0].id;
  if (!state.profile) {
    state.profile = await (await fetch(`/api/profile/new?stage=${state.stage}`)).json();
    saveState();
  }
  render();
}

init();
