// Static demo (GitHub Pages): answers the app's /api/* requests from a recording of
// one real session (demo/recording.js, made by scripts/record_demo.py), so visitors can
// click through the whole flow without a server or an API key.
// Loaded only by the built demo site, before app.js; the real app never loads it.
"use strict";
(function () {
  const rec = window.DEMO_RECORDING;
  if (!rec) return;
  window.DEMO = { persona: rec.persona, sampleImage: "demo/sample-report.png" };

  const realFetch = window.fetch.bind(window);
  const reply = (data, ms = 0) => new Promise((resolve) => setTimeout(() => resolve(
    new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } })), ms));

  // same rule as planner/session.py suggest_strengths
  function strengths(grades, margin = 5) {
    const entries = Object.entries(grades);
    if (entries.length < 2) return { strong: [], weak: [] };
    const avg = entries.reduce((t, [, v]) => t + v, 0) / entries.length;
    const ordered = entries.slice().sort((a, b) => b[1] - a[1]);
    return {
      strong: ordered.filter(([, v]) => v >= avg + margin).map(([s]) => s),
      weak: ordered.slice().reverse().filter(([, v]) => v <= avg - margin).map(([s]) => s),
    };
  }

  window.fetch = (input, init = {}) => {
    const path = new URL(typeof input === "string" ? input : input.url, location.href).pathname;
    const at = path.indexOf("/api/");
    if (at < 0) return realFetch(input, init);
    const route = path.slice(at + 5);
    const body = init.body ? JSON.parse(init.body) : {};

    if (route === "stages") return reply(rec.stages);
    if (route === "profile/new") return reply(rec.profile_new);
    if (route === "extract") return reply(rec.extract, 1800);
    if (route === "strengths") return reply(strengths(body.grades || {}), 300);
    if (route === "summary") return reply(rec.summary, 2200);
    if (route === "chat") {
      // turn 0 opens the session; after that, one recorded answer per student message
      const n = body.kickoff ? 0 : (body.history || []).filter((m) => m.role === "user").length;
      const turn = rec.turns[n];
      if (turn) return reply(turn, 1800 + Math.min(turn.reply.length, 400) * 3);
      return reply({ reply: "（展示版的錄製對話到這裡結束了，按右上角「結束會談」看看會談整理吧。）",
                     profile: body.profile, trace: [], usd: 0, seconds: 0, action_updates: [],
                     user_message: body.message }, 600);
    }
    return reply({ error: "展示版不支援這個功能" });
  };

  // a slim bar above the app so nobody mistakes the replay for live AI
  document.addEventListener("DOMContentLoaded", () => {
    const style = document.createElement("style");
    style.textContent = `
      .demo-banner { position: relative; z-index: 3; text-align: center; font-size: 13px; line-height: 32px; height: 32px;
        background: #3b2f2a; color: #fff6ec; padding: 0 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .demo-banner a { color: #ffc9a3; margin-left: 8px; }
      body.demo .layout { height: calc(100% - 72px - 32px); }
      @media (max-width: 900px) { body.demo .layout { height: calc(100% - 112px - 32px); } .demo-banner { font-size: 12px; } }`;
    document.head.appendChild(style);
    document.body.classList.add("demo");
    const bar = document.createElement("div");
    bar.className = "demo-banner";
    bar.innerHTML = `展示版：AI 回覆是預先錄製的一段真實會談<a href="https://github.com/bluedragonmy/learning-planner" target="_blank" rel="noopener">原始碼</a>`;
    document.body.prepend(bar);
  });
})();
